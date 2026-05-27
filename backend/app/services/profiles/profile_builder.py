"""Deterministic longitudinal profile snapshots from analysis + patterns."""

from __future__ import annotations

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
)
from app.services.patterns.pattern_data import load_pattern_aggregation_input
from app.services.patterns.pattern_service import list_user_patterns

MIN_GAMES_FOR_PROFILE = 10
TOP_PATTERN_REF_LIMIT = 10

_SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "significant": 3,
    "medium": 2,
    "developing": 1,
    "low": 1,
}

_PHASE_LABELS = {
    "opening": "Opening",
    "middlegame": "Middlegame",
    "endgame": "Endgame",
}


def build_player_profile(db: Session, user_id: int) -> Optional[PlayerProfile]:
    """
    Build and persist an append-only ``PlayerProfile`` snapshot.

    Aggregates Stockfish-grounded ``GameAnalysis`` rows, persisted
    ``PlayerPattern`` rows, and optional ``User.current_ratings``.
    Returns ``None`` when the user has fewer than ``MIN_GAMES_FOR_PROFILE``
    analyzed games. Does not invoke Stockfish or any LLM.
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
        profile_summary=None,
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
    rank = _SEVERITY_RANK.get(str(pattern.severity).lower(), 0)
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
