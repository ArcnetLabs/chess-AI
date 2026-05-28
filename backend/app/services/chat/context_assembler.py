"""Assemble read-only coach context from profile and pattern DB facts."""

from __future__ import annotations

import re
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.services.coaching.retrieval_service import (
    RetrievedMemory,
    format_retrieved_memories_for_context,
    retrieve_semantic_memories,
    retrieve_semantic_memories_async,
)
from app.services.patterns.pattern_service import list_user_patterns
from app.services.profiles.profile_service import get_latest_profile

# Mirrors profile_builder severity ordering for consistent top-N selection.
_SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "significant": 3,
    "medium": 2,
    "developing": 1,
    "low": 1,
}


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
    rank = _SEVERITY_RANK.get(str(pattern.severity).lower(), 0)
    return (rank, float(pattern.confidence_score))


def _rank_top_patterns(patterns: List[PlayerPattern], limit: int) -> List[PlayerPattern]:
    ranked = sorted(patterns, key=_pattern_sort_key, reverse=True)
    return ranked[:limit]


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
        lines.append("")

    all_patterns = list_user_patterns(db, user_id, limit=200)
    top = _rank_top_patterns(all_patterns, top_patterns)

    if not top:
        lines.append("Detected patterns: none persisted yet.")
    else:
        lines.append("Top detected patterns (severity, then confidence):")
        for pattern in top:
            lines.append(
                f"- pattern_id={pattern.id} "
                f"type={pattern.pattern_type}/{pattern.pattern_subtype} "
                f"severity={pattern.severity} "
                f"confidence={pattern.confidence_score:.2f}: "
                f"{pattern.pattern_description}"
            )

    memories = semantic_memories
    if memories is None and query_text:
        if content_types == []:
            memories = []
        else:
            memories = retrieve_semantic_memories(
                db, user_id, query_text, content_types=content_types
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
                db, user_id, query_text, content_types=content_types
            )

    return assemble_coach_context(
        db,
        user_id,
        top_patterns=top_patterns,
        query_text=query_text,
        content_types=content_types,
        semantic_memories=semantic_memories,
    )
