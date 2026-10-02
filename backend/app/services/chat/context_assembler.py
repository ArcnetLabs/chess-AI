"""Assemble read-only coach context from profile and pattern DB facts."""

from __future__ import annotations

import re
from typing import List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.game import Game, GameAnalysis
from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.coaching.retrieval_service import (
    RetrievedMemory,
    format_retrieved_memories_for_context,
    retrieve_semantic_memories,
    retrieve_semantic_memories_async,
)
from app.services.patterns.constants import SEVERITY_RANK
from app.services.patterns.pattern_service import list_user_patterns
from app.services.profiles.profile_service import get_latest_profile
from app.services.retrieval import DEFAULT_SEMANTIC_MIN_SIMILARITY


def extract_pattern_ids_from_context(context: str) -> List[int]:
    """Parse ``pattern_id=N`` citations from assembled coach context."""
    if not context:
        return []
    seen: set[int] = set()
    ordered: List[int] = []
    for match in re.finditer(r"pattern_id=(\d+)", context):
        pattern_id = int(match.group(1))
        if pattern_id not in seen:
            seen.add(pattern_id)
            ordered.append(pattern_id)
    return ordered


def _pattern_sort_key(pattern: PlayerPattern) -> Tuple[int, float]:
    rank = SEVERITY_RANK.get(str(pattern.severity).lower(), 0)
    return (rank, float(pattern.confidence_score))


def _rank_top_patterns(patterns: List[PlayerPattern], limit: int) -> List[PlayerPattern]:
    ranked = sorted(patterns, key=_pattern_sort_key, reverse=True)
    return ranked[:limit]


def _retrieval_limit(content_types: list[str] | None) -> int:
    """Keep per-slice depth stable when more slices are searched together."""
    slice_count = len(content_types or [])
    return 5 + 3 * max(0, slice_count - 1)


def _format_phase_performance(phase_performance: object) -> str:
    if not phase_performance or not isinstance(phase_performance, dict):
        return "unavailable"
    parts: List[str] = []
    for phase in ("opening", "middlegame", "endgame"):
        value = phase_performance.get(phase)
        if value is not None:
            parts.append(f"{phase}: {value}")
    return ", ".join(parts) if parts else "unavailable"


def _format_weaknesses(weaknesses: object) -> str:
    if not weaknesses:
        return "none recorded"
    if isinstance(weaknesses, list):
        return "; ".join(str(item) for item in weaknesses)
    return str(weaknesses)


def _live_game_counts(db: Session, user_id: int) -> dict:
    """Games actually imported and analyzed right now (not the snapshot)."""
    total = (
        db.query(func.count(Game.id)).filter(Game.user_id == user_id).scalar() or 0
    )
    analyzed = (
        db.query(func.count(GameAnalysis.id))
        .join(Game, Game.id == GameAnalysis.game_id)
        .filter(Game.user_id == user_id, Game.is_analyzed.is_(True))
        .scalar()
        or 0
    )
    return {"total": int(total), "analyzed": int(analyzed)}


def _accuracy_summary(db: Session, user_id: int) -> dict | None:
    """Accuracy across the player's analysed games: sample size, mean, median.

    The median is carried alongside the mean because a handful of disasters drag
    the mean down, and the coach was reading "average" as "how accurate you are".

    Returns ``None`` when no analysis carries an accuracy figure — an absent
    figure is reported by saying nothing, never by implying zero.
    """
    rows = (
        db.query(GameAnalysis.accuracy_percentage)
        .join(Game, Game.id == GameAnalysis.game_id)
        .filter(
            Game.user_id == user_id,
            Game.is_analyzed.is_(True),
            GameAnalysis.accuracy_percentage.isnot(None),
        )
        .all()
    )
    values = sorted(
        float(value) for (value,) in rows if value is not None
    )
    if not values:
        return None
    middle = len(values) // 2
    median = (
        values[middle]
        if len(values) % 2
        else (values[middle - 1] + values[middle]) / 2
    )
    return {
        "games": len(values),
        "mean": sum(values) / len(values),
        "median": median,
    }


# Chess.com stats payload keys, in the order a player sees them on the reveal.
_RATING_TIME_CONTROLS = (
    ("rapid", "chess_rapid"),
    ("blitz", "chess_blitz"),
    ("bullet", "chess_bullet"),
    ("daily", "chess_daily"),
)


def _current_rating_parts(current_ratings: object) -> List[str]:
    """Time-control-labelled ratings from the stored Chess.com stats payload.

    Shape is ``{"chess_rapid": {"last": {"rating": 1420}}, ...}``. Anything the
    payload does not carry is left out rather than rendered as 0 — a missing time
    control must not read as a rating of zero.
    """
    if not isinstance(current_ratings, dict):
        return []
    parts: List[str] = []
    for label, key in _RATING_TIME_CONTROLS:
        entry = current_ratings.get(key)
        if not isinstance(entry, dict):
            continue
        last = entry.get("last")
        rating = last.get("rating") if isinstance(last, dict) else None
        if isinstance(rating, (int, float)) and not isinstance(rating, bool) and rating:
            parts.append(f"{label} {int(rating)}")
    return parts


def _player_numbers_lines(db: Session, user_id: int) -> List[str]:
    """The figures the product already shows the player, as coach facts.

    Both of these are rendered to the player elsewhere in the product (the
    accuracy figure on game analysis, the four rating cards on the onboarding
    reveal), so a coach that asks for them looks like it lost the player's data.
    """
    lines: List[str] = []
    accuracy = _accuracy_summary(db, user_id)
    if accuracy is not None:
        games = accuracy["games"]
        lines.append(
            f"- Your accuracy across your analysed games: average "
            f"{accuracy['mean']:.1f}%, median {accuracy['median']:.1f}% "
            f"(from {games} analysed game{'' if games == 1 else 's'})."
        )
    user = db.query(User).filter(User.id == user_id).one_or_none()
    rating_parts = _current_rating_parts(user.current_ratings if user else None)
    if rating_parts:
        lines.append(
            "- Your current rating by time control: " + ", ".join(rating_parts) + "."
        )
    return lines


def assemble_coach_context(
    db: Session,
    user_id: int,
    *,
    top_patterns: int = 5,
    query_text: str | None = None,
    content_types: list[str] | None = None,
    semantic_memories: list[RetrievedMemory] | None = None,
) -> str:
    """
    Build a compact text block of DB-backed facts for LLM coach context.

    Does not run Stockfish or compute evaluations — only persisted analysis data.
    When ``query_text`` is provided (and ``semantic_memories`` is not), runs sync
    semantic retrieval. Pass pre-fetched ``semantic_memories`` to skip retrieval.
    """
    lines: List[str] = [
        "## Player Context (read-only facts from ChessIQ analysis)",
        "Do not invent chess evaluations; use only these facts for personalization.",
        "",
    ]

    profile: PlayerProfile | None = get_latest_profile(db, user_id)
    live_counts = _live_game_counts(db, user_id)
    lines.append(
        "Analyzed games on record right now: "
        f"{live_counts['analyzed']} analyzed of {live_counts['total']} imported. "
        "Always answer questions about how many games you have access to from this "
        "line, not from the profile snapshot below (snapshots lag the analysis run)."
    )
    lines.append("")
    # The player's own headline numbers, which the product already renders to them.
    # Without these the coach answered "I don't have your accuracy or your rating"
    # and asked the player to supply them (live end-to-end failure), because the
    # context it was given held patterns and phase averages but not these two.
    number_lines = _player_numbers_lines(db, user_id)
    if number_lines:
        lines.extend(
            [
                "## Player Numbers (read-only facts from this player's account)",
                "",
                *number_lines,
                "",
                "These figures are on record for this player. Never ask them for a "
                "number listed here.",
                "",
            ]
        )
    if profile is None:
        lines.extend(
            [
                "Profile: Not available — insufficient analyzed games for a",
                "longitudinal profile snapshot yet.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"profile_version: {profile.profile_version}",
                f"games_analyzed_count: {profile.games_analyzed_count}",
                f"archetype: {profile.archetype or 'unknown'}",
                f"phase_performance: {_format_phase_performance(profile.phase_performance)}",
                f"primary_weaknesses: {_format_weaknesses(profile.primary_weaknesses)}",
            ]
        )
        if profile.profile_summary:
            lines.append(f"profile_summary: {profile.profile_summary}")
        # Measured tendencies about *when* this player's decisions go wrong, each
        # compared against their own baseline. Stated as facts the coach may use,
        # with the numbers, so it does not have to characterise the player itself.
        for hypothesis in (profile.behavioural_hypotheses or [])[:3]:
            statement = hypothesis.get("statement") if isinstance(hypothesis, dict) else None
            if statement:
                lines.append(f"tendency: {statement}")
        lines.append("")

    all_patterns = list_user_patterns(db, user_id, limit=200)
    top = _rank_top_patterns(all_patterns, top_patterns)

    if not top:
        lines.append("Detected patterns: none persisted yet.")
    else:
        lines.append("Top detected patterns (most serious first):")
        for pattern in top:
            # "severity" is an internal field name; it is handed to the coach as context
            # and was one more word for a reply to echo back. The ranking is already
            # reflected by the order, so the label carries no information a reply needs.
            lines.append(
                f"- pattern_id={pattern.id} "
                f"type={pattern.pattern_type}/{pattern.pattern_subtype} "
                f"confidence={pattern.confidence_score:.2f}: "
                f"{pattern.pattern_description}"
            )

    memories = semantic_memories
    if memories is None and query_text:
        if content_types == []:
            memories = []
        else:
            memories = retrieve_semantic_memories(
                db,
                user_id,
                query_text,
                content_types=content_types,
                limit=_retrieval_limit(content_types),
                # Without an explicit floor every stored memory qualifies, so
                # "relevant memories" meant "some memories". See
                # services/retrieval/similar_decisions.py for the rationale.
                min_similarity=DEFAULT_SEMANTIC_MIN_SIMILARITY,
            )

    memory_block = format_retrieved_memories_for_context(memories or [])
    if memory_block:
        lines.extend(["", memory_block])

    return "\n".join(lines)


async def assemble_coach_context_async(
    db: Session,
    user_id: int,
    *,
    top_patterns: int = 5,
    query_text: str | None = None,
    content_types: list[str] | None = None,
) -> str:
    """Async context assembly with non-blocking semantic memory retrieval."""
    semantic_memories: list[RetrievedMemory] | None = None
    if query_text:
        if content_types == []:
            semantic_memories = []
        else:
            semantic_memories = await retrieve_semantic_memories_async(
                db,
                user_id,
                query_text,
                content_types=content_types,
                limit=_retrieval_limit(content_types),
            )

    return assemble_coach_context(
        db,
        user_id,
        top_patterns=top_patterns,
        query_text=query_text,
        content_types=content_types,
        semantic_memories=semantic_memories,
    )
