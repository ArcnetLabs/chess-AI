"""Training plan lifecycle operations for the /training API (redesign P6).

Complements ``drill_generator_service`` (pattern-driven generation) with the
manual paths the redesigned frontend needs: coach/interview-authored plans,
ad-hoc drill saves, and status transitions. Completion aggregation lives in
``training_progress_service`` and is reused, not duplicated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ...models.training import DrillAttempt, TrainingPlan
from .drill_generator_service import get_next_plan_version
from .training_progress_service import sync_plan_completed_count

ALLOWED_DRILL_STATUSES = {"pending", "in_progress", "completed", "skipped"}
ALLOWED_PLAN_SOURCES = {"interview", "coach", "self", "pattern_engine"}


class DrillNotFoundError(LookupError):
    """Raised when a drill does not exist for the user."""


class InvalidTransitionError(ValueError):
    """Raised on an illegal drill status transition."""


def create_manual_plan(
    db: Session,
    user_id: int,
    *,
    title: str,
    drills: List[Dict[str, Any]],
    focus_areas: Optional[List[str]] = None,
    focus_pattern_ids: Optional[List[int]] = None,
    source: str = "coach",
    plan_metadata: Optional[Dict[str, Any]] = None,
) -> TrainingPlan:
    """Create an active versioned plan plus its pending drill rows."""
    if source not in ALLOWED_PLAN_SOURCES:
        raise ValueError(f"Unknown plan source: {source}")
    if not drills:
        raise ValueError("A plan needs at least one drill")

    version = get_next_plan_version(db, user_id)
    plan = TrainingPlan(
        user_id=user_id,
        plan_version=version,
        status="active",
        title=title.strip() or f"Training plan v{version}",
        focus_areas=focus_areas or [],
        focus_pattern_ids=focus_pattern_ids or [],
        drill_count=0,
        completed_drill_count=0,
        source=source,
        plan_metadata=plan_metadata or {},
    )
    db.add(plan)
    db.flush()

    for drill in drills:
        prompt_text = str(drill.get("prompt_text") or "").strip()
        if not prompt_text:
            raise ValueError("Every drill needs prompt_text")
        db.add(
            DrillAttempt(
                user_id=user_id,
                training_plan_id=plan.id,
                pattern_id=drill.get("pattern_id"),
                drill_type=str(drill.get("drill_type") or "puzzle"),
                status="pending",
                prompt_text=prompt_text,
                position_fen=drill.get("position_fen"),
                expected_answer=drill.get("expected_answer"),
            )
        )

    plan.drill_count = len(drills)
    db.commit()
    db.refresh(plan)
    return plan


def create_adhoc_drill(
    db: Session,
    user_id: int,
    *,
    drill_type: str,
    prompt_text: str,
    position_fen: Optional[str] = None,
    pattern_id: Optional[int] = None,
    training_plan_id: Optional[int] = None,
    expected_answer: Optional[str] = None,
    attempt_metadata: Optional[Dict[str, Any]] = None,
) -> DrillAttempt:
    """Save a single drill ("save this drill" from a coach reply)."""
    if not prompt_text.strip():
        raise ValueError("prompt_text is required")

    drill = DrillAttempt(
        user_id=user_id,
        training_plan_id=training_plan_id,
        pattern_id=pattern_id,
        drill_type=drill_type or "puzzle",
        status="pending",
        prompt_text=prompt_text.strip(),
        position_fen=position_fen,
        expected_answer=expected_answer,
        attempt_metadata=attempt_metadata or {},
    )
    db.add(drill)
    if training_plan_id is not None:
        plan = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.id == training_plan_id,
                TrainingPlan.user_id == user_id,
            )
            .first()
        )
        if plan is None:
            raise DrillNotFoundError("Training plan not found for this user")
        plan.drill_count = (plan.drill_count or 0) + 1
    db.commit()
    db.refresh(drill)
    return drill


def list_plans(db: Session, user_id: int) -> List[TrainingPlan]:
    """All of the user's plans, newest version first."""
    return (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id == user_id)
        .order_by(TrainingPlan.plan_version.desc())
        .all()
    )


def get_active_plan(db: Session, user_id: int) -> Optional[TrainingPlan]:
    """The user's active plan, or ``None``."""
    return (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id == user_id, TrainingPlan.status == "active")
        .order_by(TrainingPlan.plan_version.desc())
        .first()
    )


def list_plan_drills(db: Session, user_id: int, training_plan_id: int) -> List[DrillAttempt]:
    """Drills belonging to one of the user's plans, in insertion order."""
    return (
        db.query(DrillAttempt)
        .filter(
            DrillAttempt.user_id == user_id,
            DrillAttempt.training_plan_id == training_plan_id,
        )
        .order_by(DrillAttempt.id.asc())
        .all()
    )


def _get_drill(db: Session, user_id: int, drill_id: int) -> DrillAttempt:
    drill = (
        db.query(DrillAttempt)
        .filter(DrillAttempt.id == drill_id, DrillAttempt.user_id == user_id)
        .first()
    )
    if drill is None:
        raise DrillNotFoundError(f"Drill {drill_id} not found")
    return drill


def set_drill_status(
    db: Session,
    user_id: int,
    drill_id: int,
    status: str,
) -> DrillAttempt:
    """Transition a drill to ``started``/``skipped`` (completion has its own path)."""
    if status not in {"in_progress", "skipped"}:
        raise InvalidTransitionError(
            f"Use the complete endpoint to finish a drill; cannot set status to {status!r}"
        )

    drill = _get_drill(db, user_id, drill_id)
    if drill.status == "completed":
        raise InvalidTransitionError("A completed drill cannot change status")
    if status == "skipped" and drill.status == "skipped":
        raise InvalidTransitionError("Drill is already skipped")

    drill.status = status
    if status == "in_progress" and drill.started_at is None:
        drill.started_at = datetime.now(timezone.utc)
    if drill.training_plan_id is not None:
        sync_plan_completed_count(db, drill.training_plan_id)
    db.commit()
    db.refresh(drill)
    return drill


def record_drill_attempt(
    db: Session,
    user_id: int,
    drill_id: int,
    *,
    user_answer: str,
    is_correct: bool,
    score: Optional[float] = None,
) -> DrillAttempt:
    """Complete a drill with an answer and sync plan counters."""
    drill = _get_drill(db, user_id, drill_id)
    if drill.status == "completed":
        raise InvalidTransitionError("Drill is already completed")
    if drill.status == "skipped":
        raise InvalidTransitionError("A skipped drill cannot be completed")

    drill.status = "completed"
    drill.user_answer = user_answer
    drill.is_correct = is_correct
    drill.score = score
    drill.completed_at = datetime.now(timezone.utc)
    if drill.training_plan_id is not None:
        sync_plan_completed_count(db, drill.training_plan_id)
    db.commit()
    db.refresh(drill)
    return drill
