"""Deterministic longitudinal profile snapshots from analysis + patterns."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.game import Game, GameAnalysis
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.analysis.analysis_pipeline import AnalysisPipeline
from app.services.patterns.constants import (
    MIN_OPENING_SAMPLE_GAMES,
    OPENING_ACPL_THRESHOLD,
    OPENING_SPECIFIC_ACPL_THRESHOLD,
    SEVERITY_RANK,
)
from app.services.patterns.pattern_data import load_pattern_aggregation_input
from app.services.patterns.pattern_service import list_user_patterns
from app.services.profiles.summary_composer import build_coach_summary, phase_findings

MIN_GAMES_FOR_PROFILE = 10
TOP_PATTERN_REF_LIMIT = 10

_PHASE_LABELS = {
    "opening": "Opening",
    "middlegame": "Middlegame",
    "endgame": "Endgame",
}


def build_player_profile(
    db: Session, user_id: int, *, force: bool = False
) -> Optional[PlayerProfile]:
    """
    Build and persist an append-only ``PlayerProfile`` snapshot.

    Aggregates Stockfish-grounded ``GameAnalysis`` rows, persisted
    ``PlayerPattern`` rows, and optional ``User.current_ratings``.
    Returns ``None`` when the user has fewer than ``MIN_GAMES_FOR_PROFILE``
    analyzed games. Does not invoke Stockfish or any LLM.

    When nothing material has changed since the newest snapshot (same analyzed
    game count, same pattern count, same cached ratings) the existing snapshot
    is returned instead of appending a duplicate version. Analysis batches fire
    one build per pattern-detection run, so without this guard a single 200-game
    import appended a dozen identical rows, each re-running the full-history
    aggregation on the worker.

    ``force=True`` (an explicit user-triggered rebuild) always snapshots, which
    is also how a profile built before summaries existed gets refreshed.
    """
    aggregation = load_pattern_aggregation_input(db, user_id)
    if aggregation is None or aggregation.total_analyzed_games < MIN_GAMES_FOR_PROFILE:
        count = aggregation.total_analyzed_games if aggregation else 0
        logger.info(
            f"Skipping profile snapshot for user_id={user_id}: "
            f"games_analyzed_count={count} < {MIN_GAMES_FOR_PROFILE}"
        )
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning(f"Skipping profile snapshot: user_id={user_id} not found")
        return None

    patterns = list_user_patterns(db, user_id, limit=100)
    move_quality = _load_move_quality_totals(db, user_id)
    period_start, period_end, first_game_date = _derive_game_period(aggregation.opening_by_game)

    phase_performance = _build_phase_performance(aggregation)
    opening_repertoire = _build_opening_repertoire(aggregation.opening_by_game)
    pattern_summary_refs = _build_pattern_summary_refs(patterns)
    primary_strengths, primary_weaknesses = _derive_strengths_weaknesses(
        patterns, phase_performance
    )
    style_indicators = _build_style_indicators(move_quality)
    tactical_themes = _build_tactical_themes(patterns, move_quality)
    rating_trends = _build_rating_trends(user, aggregation.opening_by_game)
    archetype = _derive_archetype(phase_performance)

    latest = _latest_profile(db, user_id)
    if (
        not force
        and latest is not None
        and _is_unchanged(
            latest,
            games_analyzed_count=aggregation.total_analyzed_games,
            patterns_detected_count=len(patterns),
            rating_trends=rating_trends,
        )
    ):
        logger.info(
            f"Skipping profile snapshot for user_id={user_id}: nothing changed "
            f"since version={latest.profile_version}"
        )
        return latest

    snapshot_at = datetime.now(timezone.utc)
    next_version = _next_profile_version(db, user_id)

    profile = PlayerProfile(
        user_id=user_id,
        profile_version=next_version,
        snapshot_at=snapshot_at,
        period_start=period_start,
        period_end=period_end,
        archetype=archetype,
        primary_strengths=primary_strengths,
        primary_weaknesses=primary_weaknesses,
        style_indicators=style_indicators,
        time_management_profile={},
        phase_performance=phase_performance,
        opening_repertoire=opening_repertoire,
        tactical_themes=tactical_themes,
        pattern_summary_refs=pattern_summary_refs,
        rating_trends=rating_trends,
        games_analyzed_count=aggregation.total_analyzed_games,
        patterns_detected_count=len(patterns),
        first_game_date=first_game_date,
        profile_summary=_build_summary(
            archetype=archetype,
            games_analyzed_count=aggregation.total_analyzed_games,
            patterns_detected_count=len(patterns),
            primary_strengths=primary_strengths,
            primary_weaknesses=primary_weaknesses,
            style_indicators=style_indicators,
            tactical_themes=tactical_themes,
            phase_performance=phase_performance,
            rating_trends=rating_trends,
        ),
        generated_at=snapshot_at,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    logger.info(
        f"Built player profile user_id={user_id} version={next_version} "
        f"games={aggregation.total_analyzed_games} patterns={len(patterns)}"
    )
    return profile


def _latest_profile(db: Session, user_id: int) -> Optional[PlayerProfile]:
    """Newest persisted snapshot for a user, or ``None`` when none exists."""
    return (
        db.query(PlayerProfile)
        .filter(PlayerProfile.user_id == user_id)
        .order_by(PlayerProfile.profile_version.desc())
        .first()
    )


def _is_unchanged(
    latest: PlayerProfile,
    *,
    games_analyzed_count: int,
    patterns_detected_count: int,
    rating_trends: Dict[str, Any],
) -> bool:
    """True when a rebuild would duplicate the newest snapshot's inputs."""
    if latest.games_analyzed_count != games_analyzed_count:
        return False
    if latest.patterns_detected_count != patterns_detected_count:
        return False
    # Cached Chess.com ratings refresh on every sync; a ratings-only change is
    # still a real change worth snapshotting.
    return _ratings_signature(latest.rating_trends) == _ratings_signature(rating_trends)


def _ratings_signature(rating_trends: Optional[Dict[str, Any]]) -> str:
    """Stable, comparable view of the live ratings inside ``rating_trends``."""
    current = (rating_trends or {}).get("current")
    try:
        return json.dumps(current, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(current)


def _build_summary(
    *,
    archetype: Optional[str],
    games_analyzed_count: int,
    patterns_detected_count: int,
    primary_strengths: Optional[List[str]],
    primary_weaknesses: Optional[List[str]],
    style_indicators: Optional[Dict[str, Any]],
    tactical_themes: Optional[Dict[str, Any]],
    phase_performance: Optional[Dict[str, Any]] = None,
    rating_trends: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Coach-voice summary for the profile headline.

    The deterministic phrasing is the ground truth written first, then handed to
    the LLM composer as its fallback — so a provider outage costs prose quality,
    never the summary itself.
    """
    deterministic = _compose_profile_summary(
        archetype=archetype,
        games_analyzed_count=games_analyzed_count,
        patterns_detected_count=patterns_detected_count,
        primary_strengths=primary_strengths,
        primary_weaknesses=primary_weaknesses,
        style_indicators=style_indicators,
        tactical_themes=tactical_themes,
        phase_performance=phase_performance,
    )
    return build_coach_summary(
        fallback=deterministic,
        archetype=archetype,
        games_analyzed_count=games_analyzed_count,
        patterns_detected_count=patterns_detected_count,
        primary_strengths=primary_strengths,
        primary_weaknesses=primary_weaknesses,
        phase_performance=phase_performance,
        tactical_themes=tactical_themes,
        style_indicators=style_indicators,
        rating_trends=rating_trends,
    )


def _compose_profile_summary(
    *,
    archetype: Optional[str],
    games_analyzed_count: int,
    patterns_detected_count: int,
    primary_strengths: Optional[List[str]],
    primary_weaknesses: Optional[List[str]],
    style_indicators: Optional[Dict[str, Any]],
    tactical_themes: Optional[Dict[str, Any]],
    phase_performance: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Deterministic coach summary from the snapshot's own aggregates.

    No LLM call: the summary is derived from the same numbers the snapshot
    stores, so it is always available the moment a profile is built (the insights
    page renders it as the card headline and the coach context includes it). Kept
    to card scale: the full weakness text, phase performance and style indicators
    reach the coach through their own fields.

    Strength and weakness come from the *phase ranking* when available, because
    that is what the archetype label is derived from — the detector's weakness
    wording comes from ACPL thresholds and can name a different phase, which made
    the headline read "Strong Opening / Weak Endgame ... main leak: opening".
    """
    games_label = f"{games_analyzed_count} analyzed game" + (
        "" if games_analyzed_count == 1 else "s"
    )
    pattern_label = f"{patterns_detected_count} recurring pattern" + (
        "" if patterns_detected_count == 1 else "s"
    )
    sentences: List[str] = [
        f"{archetype or 'Balanced profile'} across {games_label} and {pattern_label}."
    ]

    strongest_phase, weakest_phase = phase_findings(phase_performance)
    if strongest_phase and weakest_phase:
        sentences.append(f"Strongest area: your {strongest_phase} play.")
        sentences.append(f"Main leak: your {weakest_phase} play.")
    else:
        if primary_strengths:
            sentences.append(f"Strongest area: {_first_sentence(primary_strengths[0])}")
        elif not primary_weaknesses:
            sentences.append(
                "No dominant strength or weakness has cleared the detection threshold yet."
            )
        if primary_weaknesses:
            sentences.append(f"Main leak: {_first_sentence(primary_weaknesses[0])}")

    themes = tactical_themes or {}
    blunders = themes.get("blunders")
    mistakes = themes.get("mistakes")
    inaccuracies = themes.get("inaccuracies")
    if any(isinstance(value, int) for value in (blunders, mistakes, inaccuracies)):
        sentences.append(
            "Move quality: "
            f"{int(blunders or 0)} blunders, {int(mistakes or 0)} mistakes, "
            f"{int(inaccuracies or 0)} inaccuracies."
        )

    return " ".join(sentence.strip() for sentence in sentences if sentence)


def _first_sentence(text: Optional[str]) -> str:
    """Leading sentence of a verbose derived finding, for card-scale copy."""
    if not text:
        return ""
    head = text.strip().split(". ", 1)[0].strip()
    return head if head.endswith(".") else f"{head}."


def _next_profile_version(db: Session, user_id: int) -> int:
    current_max = (
        db.query(func.max(PlayerProfile.profile_version))
        .filter(PlayerProfile.user_id == user_id)
        .scalar()
    )
    return (current_max or 0) + 1


def _load_move_quality_totals(db: Session, user_id: int) -> Dict[str, int]:
    rows = (
        db.query(GameAnalysis)
        .join(Game, GameAnalysis.game_id == Game.id)
        .filter(Game.user_id == user_id, Game.is_analyzed.is_(True))
        .all()
    )
    totals = {
        "brilliant_moves": 0,
        "great_moves": 0,
        "best_moves": 0,
        "excellent_moves": 0,
        "good_moves": 0,
        "inaccuracies": 0,
        "mistakes": 0,
        "blunders": 0,
    }
    for analysis in rows:
        for key in totals:
            totals[key] += getattr(analysis, key, 0) or 0
    return totals


def _derive_game_period(
    opening_by_game: List[Dict[str, Any]],
) -> Tuple[Optional[datetime], Optional[datetime], Optional[datetime]]:
    timestamps: List[datetime] = []
    for row in opening_by_game:
        played_at = row.get("played_at")
        if not played_at:
            continue
        if isinstance(played_at, datetime):
            timestamps.append(played_at)
            continue
        try:
            timestamps.append(datetime.fromisoformat(str(played_at)))
        except ValueError:
            continue

    if not timestamps:
        return None, None, None

    timestamps.sort()
    return timestamps[0], timestamps[-1], timestamps[0]


def _average_acpl(acpls: List[float]) -> Optional[float]:
    if not acpls:
        return None
    return sum(acpls) / len(acpls)


def _build_phase_performance(aggregation) -> Dict[str, int]:
    phases = {
        "opening": aggregation.opening_acpls,
        "middlegame": aggregation.middlegame_acpls,
        "endgame": aggregation.endgame_acpls,
    }
    scores: Dict[str, int] = {}
    for phase, acpls in phases.items():
        average = _average_acpl(acpls)
        if average is None:
            continue
        scores[phase] = round(AnalysisPipeline.map_acpl_to_accuracy(average))
    return scores


def _build_opening_repertoire(opening_by_game: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Classify openings using opening-phase ACPL (not overall user ACPL)."""
    by_name: Dict[str, List[float]] = defaultdict(list)
    for row in opening_by_game:
        name = row.get("opening_name")
        opening_acpl = row.get("opening_acpl")
        if not name or opening_acpl is None:
            continue
        by_name[name].append(float(opening_acpl))

    successful: List[str] = []
    problematic: List[str] = []
    for name, acpls in sorted(by_name.items()):
        if len(acpls) < MIN_OPENING_SAMPLE_GAMES:
            continue
        average = sum(acpls) / len(acpls)
        if average <= OPENING_ACPL_THRESHOLD:
            successful.append(name)
        elif average >= OPENING_SPECIFIC_ACPL_THRESHOLD:
            problematic.append(name)

    return {"successful": successful, "problematic": problematic}


def _pattern_sort_key(pattern) -> Tuple[int, float]:
    rank = SEVERITY_RANK.get(str(pattern.severity).lower(), 0)
    return (rank, pattern.confidence_score)


def _build_pattern_summary_refs(patterns: List) -> List[Dict[str, Any]]:
    ranked = sorted(patterns, key=_pattern_sort_key, reverse=True)
    refs: List[Dict[str, Any]] = []
    for pattern in ranked[:TOP_PATTERN_REF_LIMIT]:
        refs.append(
            {
                "pattern_id": pattern.id,
                "pattern_type": pattern.pattern_type,
                "pattern_subtype": pattern.pattern_subtype,
                "severity": pattern.severity,
                "confidence": round(float(pattern.confidence_score), 4),
                "is_strength": bool(pattern.is_strength),
            }
        )
    return refs


def _derive_strengths_weaknesses(
    patterns: List,
    phase_performance: Dict[str, int],
) -> Tuple[List[str], List[str]]:
    strengths: List[str] = []
    weaknesses: List[str] = []

    for pattern in patterns:
        label = pattern.pattern_description
        if pattern.is_strength:
            strengths.append(label)
        else:
            weaknesses.append(label)

    for phase, score in phase_performance.items():
        label = _PHASE_LABELS.get(phase, phase.title())
        if score >= 80:
            strengths.append(f"Strong {label.lower()} performance ({score}/100)")
        elif score < 65:
            weaknesses.append(f"Weak {label.lower()} performance ({score}/100)")

    return _dedupe_preserve_order(strengths)[:5], _dedupe_preserve_order(weaknesses)[:5]


def _build_style_indicators(move_quality: Dict[str, int]) -> Dict[str, float]:
    sharp = (
        move_quality["brilliant_moves"]
        + move_quality["great_moves"]
        + move_quality["best_moves"]
    )
    steady = move_quality["excellent_moves"] + move_quality["good_moves"]
    errors = (
        move_quality["inaccuracies"]
        + move_quality["mistakes"]
        + move_quality["blunders"]
    )
    total = sharp + steady + errors
    if total == 0:
        return {"tactical": 0.5, "positional": 0.5, "accuracy_focus": 0.5}

    tactical = round(sharp / total, 3)
    positional = round(steady / total, 3)
    accuracy_focus = round(1.0 - (errors / total), 3)
    return {
        "tactical": tactical,
        "positional": positional,
        "accuracy_focus": accuracy_focus,
    }


def _build_tactical_themes(
    patterns: List,
    move_quality: Dict[str, int],
) -> Dict[str, int]:
    themes: Dict[str, int] = {
        "blunders": move_quality["blunders"],
        "mistakes": move_quality["mistakes"],
        "inaccuracies": move_quality["inaccuracies"],
    }
    for pattern in patterns:
        if pattern.is_strength:
            continue
        themes[pattern.pattern_subtype] = pattern.occurrence_count
    return themes


def _build_rating_trends(user: User, opening_by_game: List[Dict[str, Any]]) -> Dict[str, Any]:
    trends: Dict[str, Any] = {
        "current": user.current_ratings or {},
    }
    samples: List[Dict[str, Any]] = []
    for row in opening_by_game:
        if row.get("played_at"):
            samples.append(
                {
                    "game_id": row.get("game_id"),
                    "played_at": row.get("played_at"),
                }
            )
    if samples:
        trends["recent_games_sampled"] = len(samples)
    return trends


def _derive_archetype(phase_performance: Dict[str, int]) -> str:
    if not phase_performance:
        return "Developing Player"

    best_phase = max(phase_performance, key=phase_performance.get)
    worst_phase = min(phase_performance, key=phase_performance.get)
    spread = phase_performance[best_phase] - phase_performance[worst_phase]

    if spread < 5:
        return "Balanced Player"

    best_label = _PHASE_LABELS.get(best_phase, best_phase.title())
    worst_label = _PHASE_LABELS.get(worst_phase, worst_phase.title())
    return f"Strong {best_label} / Weak {worst_label}"


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
