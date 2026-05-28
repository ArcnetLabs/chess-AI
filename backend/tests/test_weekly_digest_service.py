"""Tests for P3-PC-01 proactive coaching weekly digest."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.game import Game, GameAnalysis
from app.models.pattern import PlayerPattern
from app.models.training import DrillAttempt, TrainingPlan
from app.models.user import User
from app.services.retention.email_delivery_service import (
    is_weekly_digest_enabled,
    send_weekly_digest_email,
)
from app.services.retention.weekly_digest_service import (
    WeeklyDigest,
    build_weekly_digest,
    render_weekly_digest_email,
)
from app.tasks.proactive_coaching_tasks import (
    scheduled_weekly_digest_dispatch_task,
    send_weekly_digest_task,
)


@pytest.fixture
def digest_owner(db):
    user = User(
        supabase_user_id="digest-user",
        chesscom_username="digestplayer",
        email="digest@example.com",
        display_name="Digest Player",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_recent_game(db, owner, *, days_ago: int = 1):
    now = datetime.now(timezone.utc)
    game = Game(
        user_id=owner.id,
        chesscom_game_id=f"digest-game-{days_ago}",
        white_username=owner.chesscom_username,
        black_username="opponent",
        white_result="win",
        black_result="resigned",
        winner="white",
        end_time=now - timedelta(days=days_ago),
        is_analyzed=True,
    )
    db.add(game)
    db.flush()
    db.add(
        GameAnalysis(
            game_id=game.id,
            user_color="white",
            user_acpl=20.0,
            accuracy_percentage=90.0,
            analysis_depth=15,
        )
    )
    db.commit()
    return game


def _add_training_plan(db, owner, *, title: str = "Endgame Focus") -> TrainingPlan:
    plan = TrainingPlan(
        user_id=owner.id,
        plan_version=1,
        status="active",
        title=title,
        drill_count=4,
        completed_drill_count=2,
        source="pattern_engine",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _add_completed_drill(
    db,
    owner,
    plan: TrainingPlan,
    *,
    days_ago: int = 2,
) -> DrillAttempt:
    now = datetime.now(timezone.utc)
    attempt = DrillAttempt(
        user_id=owner.id,
        training_plan_id=plan.id,
        drill_type="tactics",
        status="completed",
        prompt_text="Find the best move",
        completed_at=now - timedelta(days=days_ago),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def test_is_weekly_digest_enabled_defaults_true(digest_owner):
    assert is_weekly_digest_enabled(digest_owner) is True


def test_build_weekly_digest_includes_training_stats(db, digest_owner):
    _add_recent_game(db, digest_owner, days_ago=1)
    plan = _add_training_plan(db, digest_owner)
    _add_completed_drill(db, digest_owner, plan, days_ago=2)
    _add_completed_drill(db, digest_owner, plan, days_ago=10)

    db.add(
        PlayerPattern(
            user_id=digest_owner.id,
            pattern_type="blunder_cluster",
            pattern_subtype="middlegame",
            severity="high",
            confidence_score=0.85,
            occurrence_count=2,
            affected_games_count=1,
            affected_games_ratio=0.5,
            pattern_description="Repeated tactical oversights",
        )
    )
    db.commit()

    digest = build_weekly_digest(db, digest_owner.id)
    assert digest is not None
    assert digest.games_played == 1
    assert digest.drills_completed_week == 1
    assert digest.active_training_plan_title == "Endgame Focus"
    assert digest.training_completion_rate == 0.5
    assert "Blunder Cluster" in digest.coaching_tip
    assert "Repeated tactical oversights" in digest.coaching_tip


def test_build_weekly_digest_drills_count_respects_period(db, digest_owner):
    plan = _add_training_plan(db, digest_owner)
    _add_completed_drill(db, digest_owner, plan, days_ago=1)
    _add_completed_drill(db, digest_owner, plan, days_ago=3)
    _add_completed_drill(db, digest_owner, plan, days_ago=8)

    digest = build_weekly_digest(db, digest_owner.id)
    assert digest is not None
    assert digest.drills_completed_week == 2


def test_render_weekly_digest_email(db, digest_owner):
    digest = WeeklyDigest(
        user_id=digest_owner.id,
        email=digest_owner.email,
        display_name="Digest Player",
        period_start=datetime(2026, 5, 19, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 26, tzinfo=timezone.utc),
        games_played=3,
        games_analyzed=2,
        wins=2,
        losses=1,
        draws=0,
        avg_accuracy=87.0,
        avg_acpl=28.0,
        profile_archetype="Tactical",
        top_patterns=[
            {
                "pattern_type": "phase_weakness",
                "severity": "medium",
                "description": "Endgame technique gaps",
            }
        ],
        drills_completed_week=5,
        training_completion_rate=0.75,
        active_training_plan_title="Endgame Focus",
        coaching_tip="Focus area this week: Phase Weakness. Endgame technique gaps",
    )
    subject, html = render_weekly_digest_email(digest)
    assert "coaching digest" in subject
    assert "Digest Player" in html
    assert "5" in html
    assert "75%" in html
    assert "Endgame Focus" in html
    assert "Phase Weakness" in digest.coaching_tip
    assert digest.coaching_tip.split(".")[0] in html


def test_send_weekly_digest_email_skips_opt_out(digest_owner):
    digest_owner.notification_preferences = {"weekly_digest_enabled": False}
    digest = WeeklyDigest(
        user_id=digest_owner.id,
        email=digest_owner.email,
        display_name="Digest Player",
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
    )
    result = send_weekly_digest_email(digest_owner, digest)
    assert result["status"] == "skipped"
    assert result["reason"] == "weekly_digest_disabled"


def test_send_weekly_digest_email_stub_when_not_configured(digest_owner):
    digest = WeeklyDigest(
        user_id=digest_owner.id,
        email=digest_owner.email,
        display_name="Digest Player",
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
    )
    result = send_weekly_digest_email(digest_owner, digest)
    assert result["status"] == "skipped"
    assert result["reason"] == "email_delivery_not_configured"


def test_scheduled_weekly_digest_dispatch_skips_when_disabled():
    with patch("app.tasks.proactive_coaching_tasks.settings.WEEKLY_DIGEST_ENABLED", False):
        result = scheduled_weekly_digest_dispatch_task()
    assert result["status"] == "skipped"
    assert result["reason"] == "weekly_digest_disabled"


def test_scheduled_weekly_digest_dispatch_fan_out(db, digest_owner):
    with patch(
        "app.tasks.proactive_coaching_tasks.settings.WEEKLY_DIGEST_ENABLED",
        True,
    ), patch(
        "app.tasks.proactive_coaching_tasks.settings.WEEKLY_DIGEST_MAX_USERS_PER_RUN",
        10,
    ), patch(
        "app.tasks.proactive_coaching_tasks.settings.WEEKLY_DIGEST_STAGGER_SECONDS",
        0,
    ), patch(
        "app.tasks.proactive_coaching_tasks.SessionLocal",
        return_value=db,
    ), patch(
        "app.tasks.proactive_coaching_tasks.send_weekly_digest_task.apply_async",
    ) as apply_mock:
        result = scheduled_weekly_digest_dispatch_task()

    assert result["status"] == "dispatched"
    assert digest_owner.id in result["user_ids"]
    apply_mock.assert_called_once_with(args=[digest_owner.id], countdown=0)


def test_send_weekly_digest_task_skips_opted_out(db, digest_owner):
    digest_owner.notification_preferences = {"weekly_digest_enabled": False}
    db.commit()
    with patch(
        "app.tasks.proactive_coaching_tasks.SessionLocal",
        return_value=db,
    ):
        result = send_weekly_digest_task(digest_owner.id)
    assert result["status"] == "skipped"
    assert result["reason"] == "weekly_digest_disabled"
