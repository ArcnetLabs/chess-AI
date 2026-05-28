"""Tests for training progress aggregation (P3-TR-04)."""

from datetime import datetime, timezone

import pytest

from app.models.training import DrillAttempt, TrainingPlan
from app.models.user import User
from app.services.training.training_progress_service import (
    complete_drill_attempt,
    compute_training_progress,
    training_progress_to_dict,
)


def _create_user(db, **overrides) -> User:
    user = User(
        email=overrides.get("email", "progress@example.com"),
        supabase_user_id=overrides.get("supabase_user_id", "progress-sub"),
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_plan(
    db,
    user: User,
    *,
    plan_version: int = 1,
    status: str = "active",
    drill_count: int = 2,
    completed_drill_count: int = 0,
) -> TrainingPlan:
    plan = TrainingPlan(
        user_id=user.id,
        plan_version=plan_version,
        status=status,
        title=f"Plan v{plan_version}",
        drill_count=drill_count,
        completed_drill_count=completed_drill_count,
        source="pytest",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _create_attempt(
    db,
    user: User,
    *,
    training_plan_id: int | None = None,
    drill_type: str = "puzzle",
    status: str = "pending",
    completed_at: datetime | None = None,
) -> DrillAttempt:
    attempt = DrillAttempt(
        user_id=user.id,
        training_plan_id=training_plan_id,
        drill_type=drill_type,
        status=status,
        prompt_text="Find the best move.",
        completed_at=completed_at,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


class TestComputeTrainingProgress:
    def test_empty_user_returns_zero_stats(self, db):
        user = _create_user(db)

        stats = compute_training_progress(db, user.id)

        assert stats.total_drills == 0
        assert stats.completed_drills == 0
        assert stats.pending_drills == 0
        assert stats.skipped_drills == 0
        assert stats.in_progress_drills == 0
        assert stats.completion_rate == 0.0
        assert stats.active_plan_id is None
        assert stats.active_plan_version is None
        assert stats.active_plan_completion_rate is None
        assert stats.by_drill_type == {}
        assert stats.last_completed_at is None

    def test_reflects_mixed_statuses_and_drill_types(self, db):
        user = _create_user(db)
        plan = _create_plan(db, user, drill_count=4)
        completed_at = datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)

        _create_attempt(
            db,
            user,
            training_plan_id=plan.id,
            drill_type="puzzle",
            status="completed",
            completed_at=completed_at,
        )
        _create_attempt(
            db,
            user,
            training_plan_id=plan.id,
            drill_type="puzzle",
            status="pending",
        )
        _create_attempt(
            db,
            user,
            training_plan_id=plan.id,
            drill_type="endgame_technique",
            status="skipped",
        )
        _create_attempt(
            db,
            user,
            training_plan_id=plan.id,
            drill_type="endgame_technique",
            status="in_progress",
        )

        stats = compute_training_progress(db, user.id)

        assert stats.total_drills == 4
        assert stats.completed_drills == 1
        assert stats.pending_drills == 1
        assert stats.skipped_drills == 1
        assert stats.in_progress_drills == 1
        assert stats.completion_rate == 0.25
        assert stats.active_plan_id == plan.id
        assert stats.active_plan_version == plan.plan_version
        assert stats.active_plan_completion_rate == 0.25
        assert stats.by_drill_type == {
            "puzzle": {"total": 2, "completed": 1},
            "endgame_technique": {"total": 2, "completed": 0},
        }
        assert stats.last_completed_at.replace(tzinfo=timezone.utc) == completed_at


class TestCompleteDrillAttempt:
    def test_updates_attempt_and_plan_completed_count(self, db):
        user = _create_user(db)
        plan = _create_plan(db, user, drill_count=2)
        attempt = _create_attempt(db, user, training_plan_id=plan.id)

        result = complete_drill_attempt(
            db,
            attempt.id,
            user.id,
            user_answer="Nf3",
            is_correct=True,
            score=1.0,
        )

        assert result.status == "completed"
        assert result.user_answer == "Nf3"
        assert result.is_correct is True
        assert result.score == 1.0
        assert result.completed_at is not None

        db.refresh(plan)
        assert plan.completed_drill_count == 1
        assert plan.status == "active"

    def test_rejects_wrong_user(self, db):
        owner = _create_user(db, email="owner@example.com", supabase_user_id="owner-sub")
        other = _create_user(db, email="other@example.com", supabase_user_id="other-sub")
        attempt = _create_attempt(db, owner)

        with pytest.raises(ValueError, match="does not belong"):
            complete_drill_attempt(
                db,
                attempt.id,
                other.id,
                user_answer="e4",
                is_correct=False,
            )


class TestPlanCompletion:
    def test_plan_marked_completed_when_all_drills_done(self, db):
        user = _create_user(db)
        plan = _create_plan(db, user, drill_count=2)
        first = _create_attempt(db, user, training_plan_id=plan.id)
        second = _create_attempt(db, user, training_plan_id=plan.id)

        complete_drill_attempt(
            db,
            first.id,
            user.id,
            user_answer="Qh5",
            is_correct=True,
        )
        complete_drill_attempt(
            db,
            second.id,
            user.id,
            user_answer="Rd1",
            is_correct=True,
        )

        db.refresh(plan)
        assert plan.completed_drill_count == 2
        assert plan.status == "completed"

        stats = compute_training_progress(db, user.id)
        assert stats.completed_drills == 2
        assert stats.completion_rate == 1.0
        assert stats.active_plan_id is None


class TestTrainingProgressSerialization:
    def test_training_progress_to_dict_serializes_for_profile(self, db):
        user = _create_user(db)
        completed_at = datetime(2026, 5, 28, 15, 30, tzinfo=timezone.utc)
        _create_attempt(
            db,
            user,
            drill_type="puzzle",
            status="completed",
            completed_at=completed_at,
        )

        payload = training_progress_to_dict(compute_training_progress(db, user.id))

        assert payload["total_drills"] == 1
        assert payload["completed_drills"] == 1
        assert payload["completion_rate"] == 1.0
        assert payload["by_drill_type"] == {"puzzle": {"total": 1, "completed": 1}}
        assert payload["last_completed_at"].startswith("2026-05-28T15:30:00")
