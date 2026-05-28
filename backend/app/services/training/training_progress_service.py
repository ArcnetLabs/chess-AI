"""Training drill completion and progress aggregation (P3-TR-04)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.training import DrillAttempt, TrainingPlan


@dataclass
class TrainingProgressStats:
    """Aggregated drill completion stats for a user."""

    total_drills: int = 0
    completed_drills: int = 0
    pending_drills: int = 0
    skipped_drills: int = 0
    in_progress_drills: int = 0
    completion_rate: float = 0.0
    active_plan_id: Optional[int] = None
    active_plan_version: Optional[int] = None
    active_plan_completion_rate: Optional[float] = None
    by_drill_type: Dict[str, Dict[str, int]] = field(default_factory=dict)
    last_completed_at: Optional[datetime] = None


def compute_training_progress(db: Session, user_id: int) -> TrainingProgressStats:
    """Aggregate drill attempt counts and rates for ``user_id``."""
    attempts = (
        db.query(DrillAttempt)
        .filter(DrillAttempt.user_id == user_id)
        .all()
    )

    stats = TrainingProgressStats()
    stats.total_drills = len(attempts)

    by_type: Dict[str, Dict[str, int]] = {}
    last_completed: Optional[datetime] = None

    for attempt in attempts:
        status = str(attempt.status).lower()
        if status == "completed":
            stats.completed_drills += 1
            if attempt.completed_at and (
                last_completed is None or attempt.completed_at > last_completed
            ):
                last_completed = attempt.completed_at
        elif status == "pending":
            stats.pending_drills += 1
        elif status == "skipped":
            stats.skipped_drills += 1
        elif status == "in_progress":
            stats.in_progress_drills += 1

        drill_type = str(attempt.drill_type)
        bucket = by_type.setdefault(drill_type, {"total": 0, "completed": 0})
        bucket["total"] += 1
        if status == "completed":
            bucket["completed"] += 1

    stats.by_drill_type = by_type
    stats.last_completed_at = last_completed
    stats.completion_rate = (
        stats.completed_drills / stats.total_drills if stats.total_drills else 0.0
    )

    active_plan = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.status == "active",
        )
        .order_by(TrainingPlan.plan_version.desc())
        .first()
    )
    if active_plan:
        stats.active_plan_id = active_plan.id
        stats.active_plan_version = active_plan.plan_version
        if active_plan.drill_count > 0:
            completed_in_plan = (
                db.query(func.count(DrillAttempt.id))
                .filter(
                    DrillAttempt.training_plan_id == active_plan.id,
                    DrillAttempt.status == "completed",
                )
                .scalar()
            ) or 0
            stats.active_plan_completion_rate = completed_in_plan / active_plan.drill_count

    return stats


def complete_drill_attempt(
    db: Session,
    attempt_id: int,
    user_id: int,
    *,
    user_answer: str,
    is_correct: bool,
    score: float | None = None,
) -> DrillAttempt:
    """Mark a drill attempt completed and sync its training plan counters."""
    attempt = db.query(DrillAttempt).filter(DrillAttempt.id == attempt_id).first()
    if attempt is None:
        raise ValueError(f"Drill attempt {attempt_id} not found")
    if attempt.user_id != user_id:
        raise ValueError("Drill attempt does not belong to this user")

    attempt.status = "completed"
    attempt.user_answer = user_answer
    attempt.is_correct = is_correct
    attempt.score = score
    attempt.completed_at = datetime.now(timezone.utc)

    if attempt.training_plan_id is not None:
        _sync_plan_completed_count(db, attempt.training_plan_id)

    db.commit()
    db.refresh(attempt)
    return attempt


def _sync_plan_completed_count(db: Session, training_plan_id: int) -> None:
    """Update plan completed count and mark plan completed when all drills are done."""
    db.flush()

    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.id == training_plan_id)
        .first()
    )
    if plan is None:
        return

    completed_count = (
        db.query(func.count(DrillAttempt.id))
        .filter(
            DrillAttempt.training_plan_id == training_plan_id,
            DrillAttempt.status == "completed",
        )
        .scalar()
    ) or 0

    plan.completed_drill_count = int(completed_count)
    if plan.drill_count > 0 and plan.completed_drill_count >= plan.drill_count:
        plan.status = "completed"


def training_progress_to_dict(stats: TrainingProgressStats) -> dict[str, Any]:
    """Serialize progress stats for JSON API responses."""
    return {
        "total_drills": stats.total_drills,
        "completed_drills": stats.completed_drills,
        "pending_drills": stats.pending_drills,
        "skipped_drills": stats.skipped_drills,
        "in_progress_drills": stats.in_progress_drills,
        "completion_rate": stats.completion_rate,
        "active_plan_id": stats.active_plan_id,
        "active_plan_version": stats.active_plan_version,
        "active_plan_completion_rate": stats.active_plan_completion_rate,
        "by_drill_type": stats.by_drill_type,
        "last_completed_at": (
            stats.last_completed_at.isoformat() if stats.last_completed_at else None
        ),
    }
