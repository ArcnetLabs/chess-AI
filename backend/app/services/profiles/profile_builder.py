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
from app.models.game_move import GameMove
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.analysis.analysis_pipeline import AnalysisPipeline
from app.services.coaching.interventions import coaching_history_summary
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

# A phase score is map_acpl_to_accuracy over the phase's average loss per move, so
# these read as relative standings and are worded as such ("least/costliest of your
# phases") rather than as verdicts about the phase. See _derive_strengths_weaknesses.
PHASE_STRENGTH_SCORE = 80
PHASE_WEAKNESS_SCORE = 65

# The analyzer's own vocabulary for a move that cost something real. Kept as a set
# so the opening view counts errors the same way the rest of the system does.
SERIOUS_CLASSIFICATIONS = {"mistake", "blunder"}

# How deep an opening sequence has to be before counting it as "a line you played".
# Four plies is where a group still holds enough games to mean something on real
# data; deeper and one player's 143 games split into 137 groups of one.
REPERTOIRE_DEPTH_PLIES = 4
# A repertoire counts as settled when one line is this common, or holds this share.
REPERTOIRE_MIN_GAMES = 8
REPERTOIRE_TOP_SHARE = 0.25


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
    # Openings are also recorded by structure, which is the actionable view. The
    # name-based lists above stay for compatibility with existing consumers.
    opening_repertoire["by_structure"] = _build_opening_structures(
        db,
        user_id,
        patterns,
        {
            row.get("game_id"): row.get("opening_name")
            for row in aggregation.opening_by_game
            if row.get("game_id") is not None
        },
    )
    pattern_summary_refs = _build_pattern_summary_refs(patterns)
    primary_strengths, primary_weaknesses = _derive_strengths_weaknesses(
        patterns, phase_performance
    )
    style_indicators = _build_style_indicators(move_quality)
    tactical_themes = _build_tactical_themes(patterns, move_quality)
    rating_trends = _build_rating_trends(user, aggregation.opening_by_game)
    archetype = _derive_archetype(phase_performance)

    # Behavioural hypotheses are measured from the same decision series the pattern
    # engine uses, then attached to the patterns that fired in their own situations.
    # Contained: a failure here must not cost the whole snapshot.
    try:
        from app.services.patterns.event_pattern_detector import load_decisions
        from app.services.profiles.behavioural_hypotheses import (
            build_behavioural_hypotheses,
        )

        behavioural_hypotheses = build_behavioural_hypotheses(
            load_decisions(db, user_id), patterns
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Behavioural hypotheses failed for user_id={user_id}: {exc}")
        behavioural_hypotheses = []

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
        # What coaching has already been offered for these weaknesses and whether
        # it moved anything. Part of the snapshot because the coach loads the
        # snapshot, and repeating advice the player already received is the
        # failure mode this exists to prevent.
        coaching_history=coaching_history_summary(db, user_id, limit=10),
        behavioural_hypotheses=behavioural_hypotheses,
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

    The ranking is then stated as a *comparison* ("you lose the least ground in the
    opening and the most in the endgame") rather than as a verdict about either
    phase. The ranking measures average loss per move, so a phase can rank best and
    still be over the detector's absolute bar; a comparative sentence and the
    detector's magnitude sentence are both true of that phase, where "Strongest
    area: your opening play" and "your openings are where you give ground" are not.
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
        # One comparative sentence, deliberately. The phases are ranked by average
        # loss per move, so the only claim this data supports is a comparison with
        # the player's *other* phases. "Strongest area: your opening play" was an
        # absolute verdict about the opening, and on the same profile the phase
        # detector called that opening expensive in 26 games — two mutually exclusive
        # statements about one phase. A comparison cannot contradict a magnitude
        # claim, so the two surfaces agree by construction. Kept to one sentence:
        # the insights card renders this whole string as its headline.
        sentences.append(
            f"Compared with your other phases, you lose the least ground in the "
            f"{strongest_phase} and the most in the {weakest_phase}."
        )
    else:
        if primary_strengths:
            sentences.append(f"Where you hold up: {_first_sentence(primary_strengths[0])}")
        elif not primary_weaknesses:
            sentences.append(
                "No dominant strength or weakness has cleared the detection threshold yet."
            )
        if primary_weaknesses:
            sentences.append(f"Where it costs you: {_first_sentence(primary_weaknesses[0])}")

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


def _structure_of_game(rows: List[Any]) -> Optional[str]:
    """The structure the player had settled into by the end of the opening.

    The *last* opening ply rather than the first: the first few moves are book and
    nearly identical across games, so keying on them would group unrelated games
    together. The structure at the end of the opening is what the player then has
    to play, which is the thing coaching can act on.
    """
    keyed = [row for row in rows if row.structure_key]
    if not keyed:
        return None
    return max(keyed, key=lambda row: row.ply).structure_key


def _build_repertoire_stability(
    by_game: Dict[int, List[Any]],
    *,
    depth: int = REPERTOIRE_DEPTH_PLIES,
) -> Dict[str, Any]:
    """How settled the player's openings are — measured, not assumed.

    Exact structures turned out to be useless as an opening key at real data
    volume: one player's 143 games reached **136 distinct structures**, so every
    group was a single game and no claim could be supported. The useful question is
    not "which structure" but "is there a repertoire at all?", and that is
    answerable from the stored move sequences: count how concentrated the first few
    plies are.

    Measured for that player at the time of writing:

    | Depth | Distinct lines | Largest group |
    |---|---|---|
    | 2 plies | 19 | 84 |
    | 4 plies | 69 | 17 |
    | 6 plies | 111 | 6 |
    | 8 plies | 137 | 2 |

    Depth 4 is the point where a group is still big enough to mean something, so
    that is the default. When even that scatters, the honest coaching statement is
    that there is no repertoire yet — which is exactly the gap ChessReps exists to
    close, and is far more useful than a table of one-game groups.
    """
    lines: List[Tuple[str, ...]] = []
    for game_rows in by_game.values():
        ordered = sorted(game_rows, key=lambda row: row.ply)
        moves = tuple(str(row.move_uci or "") for row in ordered[:depth])
        if any(moves):
            lines.append(moves)

    if not lines:
        return {"depth": depth, "games": 0, "distinct_lines": 0, "settled": False, "statement": None}

    counts = defaultdict(int)
    for moves in lines:
        counts[moves] += 1
    largest = max(counts.values())
    top_share = round(largest / len(lines), 3)
    distinct = len(counts)

    # Two separate facts, because they mean different things and can disagree: a
    # player can have a genuine main line (worth preparing) while the repertoire as
    # a whole is scattered (worth consolidating). Real data showed exactly that —
    # 17 games on one line, across 69 lines in 143 games — so a single boolean would
    # have had to lie about one of them.
    has_main_line = largest >= REPERTOIRE_MIN_GAMES
    if top_share >= REPERTOIRE_TOP_SHARE:
        verdict = "settled"
    elif has_main_line:
        verdict = "main_line_only"
    else:
        verdict = "no_repertoire"

    if verdict == "settled":
        statement = (
            f"Your most-played opening line covers {largest} of your {len(lines)} games "
            f"({round(top_share * 100)}%) — a repertoire worth preparing properly."
        )
    elif verdict == "main_line_only":
        statement = (
            f"You have one main opening line ({largest} games), but {distinct} different "
            f"lines in {len(lines)} games overall — too spread out for openings to repeat "
            f"and be corrected."
        )
    else:
        statement = (
            f"You have played {distinct} different opening lines in {len(lines)} games; "
            f"your most common appears {largest} times. Openings repeat too little for a "
            f"repertoire pattern to show up yet."
        )

    return {
        "depth": depth,
        "games": len(lines),
        "distinct_lines": distinct,
        "largest_group": largest,
        "top_share": top_share,
        "verdict": verdict,
        "settled": verdict == "settled",
        "statement": statement,
    }


def _build_opening_structures(
    db: Session,
    user_id: int,
    patterns: List[Any],
    opening_names_by_game: Dict[int, str],
) -> Dict[str, Any]:
    """Openings keyed by the structure the player actually reaches.

    The name-string view (kept alongside this for compatibility) says "you score
    badly in the French Defense", which is not actionable: one opening name covers
    several structures with different plans, and the same structure arrives from
    different names. Keying on ``structure_key`` — the pawn skeleton and side to
    move, computed in the move layer — answers the question a coach would ask:
    *in this kind of position, how do you actually do?*

    Everything here is measured from stored rows: no engine call, no model.
    """
    rows = (
        db.query(
            GameMove.game_id,
            GameMove.ply,
            GameMove.move_uci,
            GameMove.structure_key,
            GameMove.color,
            GameMove.is_user_move,
            GameMove.classification,
            Game.winner,
        )
        .join(Game, Game.id == GameMove.game_id)
        .filter(GameMove.user_id == user_id, GameMove.phase == "opening")
        .all()
    )

    by_game: Dict[int, List[Any]] = defaultdict(list)
    for row in rows:
        by_game[row.game_id].append(row)

    buckets: Dict[str, Dict[str, Any]] = {}
    for game_id, game_rows in by_game.items():
        structure = _structure_of_game(game_rows)
        if structure is None:
            continue
        bucket = buckets.setdefault(
            structure,
            {
                "structure_key": structure,
                "games": 0,
                "user_moves": 0,
                "opening_errors": 0,
                "_score_points": [],
                "_names": defaultdict(int),
            },
        )
        bucket["games"] += 1

        user_rows = [row for row in game_rows if row.is_user_move]
        bucket["user_moves"] += len(user_rows)
        bucket["opening_errors"] += sum(
            1 for row in user_rows if str(row.classification or "").lower() in SERIOUS_CLASSIFICATIONS
        )

        name = opening_names_by_game.get(game_id)
        if name:
            bucket["_names"][name] += 1

        # Score from the player's own side, using the stored winner.
        winner = (game_rows[0].winner or "").lower()
        if winner == "draw":
            bucket["_score_points"].append(0.5)
        elif winner in ("white", "black"):
            # The player's colour in this game, read from their own moves.
            colour = _player_colour(game_rows)
            if colour:
                bucket["_score_points"].append(1.0 if winner == colour else 0.0)

    structures: List[Dict[str, Any]] = []
    for bucket in buckets.values():
        points = bucket.pop("_score_points")
        names = bucket.pop("_names")
        moves = bucket["user_moves"] or 0
        errors = bucket["opening_errors"]
        structures.append(
            {
                **bucket,
                "error_rate": round(errors / moves, 4) if moves else None,
                "score_rate": round(sum(points) / len(points), 3) if points else None,
                "opening_names": [name for name, _ in sorted(names.items(), key=lambda kv: -kv[1])][:3],
                "pattern_ids": _pattern_ids_for_structure(patterns, bucket["structure_key"]),
                "sample_sufficient": bucket["games"] >= MIN_OPENING_SAMPLE_GAMES,
            }
        )

    structures.sort(key=lambda item: (item["games"], item["structure_key"]), reverse=True)
    return {
        "method": "structure_key",
        "structures": structures,
        # Why a structure table alone is not enough: at this data volume most groups
        # hold a single game, so the honest framing is whether a repertoire exists.
        "repertoire": _build_repertoire_stability(by_game),
        "explanation": (
            "Grouped by the position structure the player reaches by the end of the "
            "opening, not by opening name: the same name covers different structures, "
            "and the same structure arises from different names. Groups are flagged "
            "when the sample is too thin to judge."
        ),
    }


def _player_colour(rows: List[Any]) -> Optional[str]:
    """The player's colour in a game, read from the moves they made."""
    for row in rows:
        if row.is_user_move and getattr(row, "color", None):
            return str(row.color).lower()
    return None


def _pattern_ids_for_structure(patterns: List[Any], structure_key: str) -> List[int]:
    """Patterns whose stored evidence names this structure.

    The link already exists in the pattern evidence (``structures``), so this reads
    it rather than re-deriving similarity: a pattern that never fired in this
    structure must not be attached to it.
    """
    matches: List[int] = []
    for pattern in patterns:
        evidence = pattern.evidence or {}
        for entry in evidence.get("structures") or []:
            key = entry.get("structure_key") if isinstance(entry, dict) else None
            if key == structure_key:
                matches.append(pattern.id)
                break
    return matches


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

    # Phase scores are a *relative* reading: ``_build_phase_performance`` maps the
    # phase's average loss per move onto the analyzer's 0-100 scale, and the number
    # says how the phase sits against the player's other phases, not against a fixed
    # bar. So a phase can score well here and still carry a magnitude leak — the
    # phase weakness detector fires on an absolute average above its own threshold —
    # and both statements are true at once. The wording has to keep the axes apart,
    # because the version this replaced did not:
    #
    #   * a phase score is a *relative magnitude* claim (compared with the other
    #     phases),
    #   * ``phase_weakness_detector`` is an *absolute magnitude* claim, scoped to the
    #     games the phase went wrong in,
    #   * ``detect_strengths`` is a *rate* claim (how often errors happen there).
    #
    # "Strong opening performance (82/100)" next to the detector's "your openings are
    # where you give ground" was the shipped contradiction: opening ACPL 46.6 maps to
    # 82/100 *and* sits above the 30.0 detector bar, so the two labels fired together
    # and denied each other. Naming the phases relatively fixes it structurally —
    # "least costly of your phases" cannot contradict "expensive in 26 games".
    #
    # Only the best and the worst phase are named, so the comparative wording is never
    # claimed by two phases at once, and only when there are at least two phases to
    # compare: with one phase it would be both the least and the most costly.
    if len(phase_performance) >= 2:
        best_phase = max(phase_performance, key=phase_performance.get)
        worst_phase = min(phase_performance, key=phase_performance.get)
        best_score = phase_performance[best_phase]
        worst_score = phase_performance[worst_phase]
        if best_score >= PHASE_STRENGTH_SCORE:
            label = _PHASE_LABELS.get(best_phase, best_phase.title()).lower()
            strengths.append(
                f"Least costly of your phases: your {label} ({best_score}/100)"
            )
        if worst_score < PHASE_WEAKNESS_SCORE:
            label = _PHASE_LABELS.get(worst_phase, worst_phase.title()).lower()
            weaknesses.append(
                f"Costliest of your phases: your {label} ({worst_score}/100)"
            )

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
    """Label the player's best and worst phase, as a comparison rather than a grade.

    The score behind each phase is ``map_acpl_to_accuracy`` over the phase's average
    loss per move, so it ranks the phases against each other. "Strong Opening / Weak
    Endgame" read as an absolute grade and contradicted the phase weakness detector,
    which fires on the same opening whenever its average loss clears 30.0 — a real
    player had opening ACPL 46.6, scoring 82/100 *and* flagged as a leak. "Least
    Costly ... / Costliest ..." says the same thing about the ranking without
    claiming the phase is good or bad, so the two can be read side by side.
    """
    if not phase_performance:
        return "Developing Player"

    best_phase = max(phase_performance, key=phase_performance.get)
    worst_phase = min(phase_performance, key=phase_performance.get)
    spread = phase_performance[best_phase] - phase_performance[worst_phase]

    if spread < 5:
        return "Balanced Player"

    best_label = _PHASE_LABELS.get(best_phase, best_phase.title())
    worst_label = _PHASE_LABELS.get(worst_phase, worst_phase.title())
    return f"Least Costly {best_label} / Costliest {worst_label}"


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
