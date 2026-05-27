"""Assemble read-only coach context from profile and pattern DB facts."""

from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
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
) -> str:
    """
    Build a compact text block of DB-backed facts for LLM coach context.

    Does not run Stockfish or compute evaluations — only persisted analysis data.
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

    return "\n".join(lines)
