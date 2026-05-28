"""P3-TR-01 — training_plans and drill_attempts model/schema tests."""
import os

from sqlalchemy import inspect

from app.models.training import DrillAttempt, TrainingPlan
from app.models.user import User


def test_training_plan_model_imports():
    assert TrainingPlan.__tablename__ == "training_plans"
    assert DrillAttempt.__tablename__ == "drill_attempts"


def test_training_plan_table_columns():
    plan_cols = {c.key for c in inspect(TrainingPlan).columns}
    expected_plan = {
        "id",
        "user_id",
        "plan_version",
        "status",
        "title",
        "focus_pattern_ids",
        "focus_areas",
        "drill_count",
        "completed_drill_count",
        "source",
        "plan_metadata",
        "generated_at",
        "created_at",
        "updated_at",
    }
    assert expected_plan.issubset(plan_cols)

    attempt_cols = {c.key for c in inspect(DrillAttempt).columns}
    expected_attempt = {
        "id",
        "user_id",
        "training_plan_id",
        "pattern_id",
        "drill_type",
        "status",
        "prompt_text",
        "position_fen",
        "expected_answer",
        "user_answer",
        "is_correct",
        "score",
        "attempt_metadata",
        "started_at",
        "completed_at",
        "created_at",
    }
    assert expected_attempt.issubset(attempt_cols)


def test_training_plan_sqlite_round_trip(db):
    """ORM round-trip on in-memory SQLite for plan + linked drill."""
    assert os.getenv("TESTING") == "1"

    user = User(
        chesscom_username="training_plan_test_user",
        email="training@test.example",
    )
    db.add(user)
    db.flush()

    plan = TrainingPlan(
        user_id=user.id,
        plan_version=1,
        status="active",
        title="Knight fork remediation",
        focus_pattern_ids=[1, 2],
        focus_areas={"opening": "sicilian"},
        drill_count=3,
        completed_drill_count=0,
        source="pattern_engine",
        plan_metadata={"generator": "pytest"},
    )
    db.add(plan)
    db.flush()

    attempt = DrillAttempt(
        user_id=user.id,
        training_plan_id=plan.id,
        drill_type="puzzle",
        status="pending",
        prompt_text="Find the knight fork.",
        position_fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
        attempt_metadata={"difficulty": "medium"},
    )
    db.add(attempt)
    db.commit()
    db.refresh(plan)
    db.refresh(attempt)

    assert plan.id is not None
    assert plan.user_id == user.id
    assert plan.plan_version == 1
    assert plan.focus_pattern_ids == [1, 2]
    assert plan.plan_metadata["generator"] == "pytest"

    assert attempt.id is not None
    assert attempt.training_plan_id == plan.id
    assert attempt.user_id == user.id
    assert attempt.attempt_metadata["difficulty"] == "medium"
