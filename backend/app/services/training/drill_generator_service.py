"""Pattern-driven training plan and drill generation (P3-TR-02)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.pattern import PatternOccurrence, PlayerPattern
from app.models.training import DrillAttempt, TrainingPlan
from app.services.patterns.pattern_service import list_user_patterns

# Mirrors context_assembler / profile_builder severity ordering.
_SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "significant": 3,
    "medium": 2,
    "developing": 1,
    "low": 1,
}

_SUBTYPE_DRILL_FALLBACK: Dict[str, str] = {
    "high_opening_acpl": "opening_repertoire",
    "high_middlegame_acpl": "middlegame_calculation",
    "high_endgame_acpl": "endgame_technique",
    "opening": "opening_repertoire",
    "middlegame": "middlegame_calculation",
    "endgame": "endgame_technique",
}

_DEFAULT_DRILL_TYPE = "puzzle"


def _pattern_sort_key(pattern: PlayerPattern) -> Tuple[int, float]:
    rank = _SEVERITY_RANK.get(str(pattern.severity).lower(), 0)
    return (rank, float(pattern.confidence_score))


def get_next_plan_version(db: Session, user_id: int) -> int:
    """Return max existing ``plan_version`` + 1, or 1 when none exist."""
    current_max = (
        db.query(func.max(TrainingPlan.plan_version))
        .filter(TrainingPlan.user_id == user_id)
        .scalar()
    )
    return int(current_max or 0) + 1


def select_patterns_for_drills(
    db: Session,
    user_id: int,
    *,
    limit: int = 5,
) -> List[PlayerPattern]:
    """
    Select weakness patterns ranked by severity then confidence.

    Uses ``list_user_patterns`` for retrieval; excludes strength rows.
    """
    patterns = list_user_patterns(db, user_id, limit=200)
    weaknesses = [p for p in patterns if not p.is_strength]
    ranked = sorted(weaknesses, key=_pattern_sort_key, reverse=True)
    return ranked[:limit]


def build_drill_prompt(
    pattern: PlayerPattern,
    occurrence: PatternOccurrence | None = None,
) -> str:
    """Template-based drill narrative (no LLM)."""
    lines = [
        f"Study focus: {pattern.pattern_description}",
        f"Pattern: {pattern.pattern_type} / {pattern.pattern_subtype}",
        f"Severity: {pattern.severity}",
    ]
    phase = None
    if occurrence:
        phase = occurrence.game_phase
        if occurrence.context_description:
            lines.append(f"Context: {occurrence.context_description}")
    if phase:
        lines.append(f"Phase: {phase}")
    elif _phase_from_subtype(pattern.pattern_subtype):
        lines.append(f"Phase: {_phase_from_subtype(pattern.pattern_subtype)}")
    return "\n".join(lines)


def _phase_from_subtype(subtype: str) -> Optional[str]:
    lowered = str(subtype).lower()
    for phase in ("opening", "middlegame", "endgame"):
        if phase in lowered:
            return phase
    return None


def resolve_drill_type(pattern: PlayerPattern) -> str:
    """``recommended_drill_type`` or subtype fallback map."""
    if pattern.recommended_drill_type:
        return str(pattern.recommended_drill_type)
    subtype = str(pattern.pattern_subtype).lower()
    if subtype in _SUBTYPE_DRILL_FALLBACK:
        return _SUBTYPE_DRILL_FALLBACK[subtype]
    for key, drill_type in _SUBTYPE_DRILL_FALLBACK.items():
        if key in subtype:
            return drill_type
    return _DEFAULT_DRILL_TYPE


def _first_example_fen(pattern: PlayerPattern) -> Optional[str]:
    positions = pattern.example_positions
    if not positions or not isinstance(positions, list):
        return None
    for item in positions:
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def pick_best_occurrence(
    db: Session,
    pattern: PlayerPattern,
) -> Optional[PatternOccurrence]:
    """Prefer occurrence with ``fen_before`` and ``best_move``; else first."""
    occurrences = (
        db.query(PatternOccurrence)
        .filter(PatternOccurrence.pattern_id == pattern.id)
        .order_by(PatternOccurrence.detected_at.desc())
        .all()
    )
    if not occurrences:
        return None
    for occurrence in occurrences:
        if occurrence.fen_before and occurrence.best_move:
            return occurrence
    return occurrences[0]


def build_drill_attempt_row(
    db: Session,
    user_id: int,
    pattern: PlayerPattern,
    training_plan_id: int,
    occurrence: PatternOccurrence | None = None,
) -> DrillAttempt:
    """Build an unsaved ``DrillAttempt`` for the given pattern."""
    if occurrence is None:
        occurrence = pick_best_occurrence(db, pattern)

    position_fen = None
    if occurrence and occurrence.fen_before:
        position_fen = occurrence.fen_before
    else:
        position_fen = _first_example_fen(pattern)

    expected_answer = occurrence.best_move if occurrence else None

    metadata: Dict[str, Any] = {
        "pattern_id": pattern.id,
        "pattern_type": pattern.pattern_type,
        "pattern_subtype": pattern.pattern_subtype,
        "severity": pattern.severity,
    }
    if occurrence:
        metadata["occurrence_id"] = occurrence.id
        if occurrence.game_phase:
            metadata["game_phase"] = occurrence.game_phase

    return DrillAttempt(
        user_id=user_id,
        training_plan_id=training_plan_id,
        pattern_id=pattern.id,
        drill_type=resolve_drill_type(pattern),
        status="pending",
        prompt_text=build_drill_prompt(pattern, occurrence),
        position_fen=position_fen,
        expected_answer=expected_answer,
        attempt_metadata=metadata,
    )


def _collect_focus_areas(
    patterns: List[PlayerPattern],
    occurrences_by_pattern: Dict[int, Optional[PatternOccurrence]],
) -> List[str]:
    areas: List[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for value in (pattern.pattern_subtype, _phase_from_subtype(pattern.pattern_subtype)):
            if value and value not in seen:
                seen.add(value)
                areas.append(value)
        occurrence = occurrences_by_pattern.get(pattern.id)
        if occurrence and occurrence.game_phase and occurrence.game_phase not in seen:
            seen.add(occurrence.game_phase)
            areas.append(occurrence.game_phase)
    return areas


def _plan_title(version: int, top_pattern: Optional[PlayerPattern]) -> str:
    if top_pattern and top_pattern.pattern_description:
        desc = top_pattern.pattern_description.strip()
        if len(desc) <= 80:
            return desc
        return f"{desc[:77]}..."
    return f"Training plan v{version}"


def generate_training_plan(
    db: Session,
    user_id: int,
    *,
    max_drills: int = 5,
    source: str = "pattern_engine",
) -> Optional[TrainingPlan]:
    """
    Create an active ``TrainingPlan`` and linked ``DrillAttempt`` rows.

    Returns ``None`` when the user has no eligible weakness patterns.
    """
    selected = select_patterns_for_drills(db, user_id, limit=max_drills)
    if not selected:
        return None

    version = get_next_plan_version(db, user_id)
    occurrences_by_pattern: Dict[int, Optional[PatternOccurrence]] = {
        pattern.id: pick_best_occurrence(db, pattern) for pattern in selected
    }

    plan = TrainingPlan(
        user_id=user_id,
        plan_version=version,
        status="active",
        title=_plan_title(version, selected[0]),
        focus_pattern_ids=[p.id for p in selected],
        focus_areas=_collect_focus_areas(selected, occurrences_by_pattern),
        drill_count=0,
        completed_drill_count=0,
        source=source,
        plan_metadata={"generator": "drill_generator_service", "pattern_count": len(selected)},
    )
    db.add(plan)
    db.flush()

    attempts: List[DrillAttempt] = []
    for pattern in selected:
        occurrence = occurrences_by_pattern.get(pattern.id)
        attempt = build_drill_attempt_row(
            db,
            user_id,
            pattern,
            plan.id,
            occurrence=occurrence,
        )
        db.add(attempt)
        attempts.append(attempt)

    plan.drill_count = len(attempts)
    db.commit()
    db.refresh(plan)
    logger.info(
        f"Generated training plan id={plan.id} user_id={user_id} "
        f"version={version} drills={plan.drill_count}"
    )
    return plan
