"""Tests for P2-RT-02 weekly summary email stub."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.game import Game, GameAnalysis
from app.models.pattern import PlayerPattern
from app.models.profile import PlayerProfile
from app.models.user import User
from app.services.retention.email_delivery_service import (
    is_email_delivery_configured,
    is_weekly_email_enabled,
    send_weekly_summary_email,
)
from app.services.retention.weekly_summary_service import (
    WeeklySummary,
    build_weekly_summary,
    render_weekly_summary_email,
)
from app.tasks.retention_tasks import (
    scheduled_weekly_summary_dispatch_task,
    send_weekly_summary_task,
)


@pytest.fixture
def owner(db):
    user = User(
        supabase_user_id="weekly-user",
        chesscom_username="weeklyplayer",
        email="weekly@example.com",
        display_name="Weekly Player",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_game_with_analysis(db, owner, *, days_ago: int = 1, winner: str = "white"):
    now = datetime.now(timezone.utc)
    end_time = now - timedelta(days=days_ago)
    game = Game(
        user_id=owner.id,
        chesscom_game_id=f"weekly-game-{days_ago}",
        white_username=owner.chesscom_username,
        black_username="opponent",
        white_result="win" if winner == "white" else "resigned",
        black_result="resigned" if winner == "white" else "win",
        winner=winner,
        end_time=end_time,
        is_analyzed=True,
    )
    db.add(game)
    db.flush()
    db.add(
        GameAnalysis(
            game_id=game.id,
            user_color="white",
            user_acpl=25.0,
            accuracy_percentage=88.5,
            analysis_depth=15,
        )
    )
    db.commit()
    return game


def test_is_weekly_email_enabled_defaults_true(owner):
    assert is_weekly_email_enabled(owner) is True


def test_is_weekly_email_enabled_respects_preference(owner):
    owner.notification_preferences = {"weekly_summary_enabled": False}
    assert is_weekly_email_enabled(owner) is False


def test_is_email_delivery_configured_false_by_default():
    assert is_email_delivery_configured() is False


def test_build_weekly_summary_aggregates_last_seven_days(db, owner):
    _add_game_with_analysis(db, owner, days_ago=2)
    _add_game_with_analysis(db, owner, days_ago=10, winner="black")

    profile = PlayerProfile(
        user_id=owner.id,
        profile_version=1,
        snapshot_at=datetime.now(timezone.utc),
        archetype="Tactical Grinder",
        games_analyzed_count=5,
        patterns_detected_count=2,
    )
    db.add(profile)
    db.add(
        PlayerPattern(
            user_id=owner.id,
            pattern_type="blunder_cluster",
            pattern_subtype="middlegame",
            severity="high",
            confidence_score=0.9,
            occurrence_count=3,
            affected_games_count=2,
            affected_games_ratio=0.4,
            pattern_description="Repeated late-game blunders",
        )
    )
    db.commit()

    summary = build_weekly_summary(db, owner.id)
    assert summary is not None
    assert summary.games_played == 1
    assert summary.games_analyzed == 1
    assert summary.wins == 1
    assert summary.avg_accuracy == 88.5
    assert summary.profile_archetype == "Tactical Grinder"
    assert len(summary.top_patterns) == 1


def test_build_weekly_summary_returns_none_without_email(db):
    user = User(supabase_user_id="no-email", chesscom_username="anon")
    db.add(user)
    db.commit()
    assert build_weekly_summary(db, user.id) is None


def test_render_weekly_summary_email(db, owner):
    summary = WeeklySummary(
        user_id=owner.id,
        email=owner.email,
        display_name="Weekly Player",
        period_start=datetime(2026, 5, 19, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 26, tzinfo=timezone.utc),
        games_played=4,
        games_analyzed=3,
        wins=2,
        losses=1,
        draws=1,
        avg_accuracy=85.0,
        avg_acpl=30.0,
        profile_archetype="Positional",
        top_patterns=[
            {
                "pattern_type": "phase_weakness",
                "severity": "medium",
                "description": "Endgame technique gaps",
            }
        ],
    )
    subject, html = render_weekly_summary_email(summary)
    assert "ChessIQ week in review" in subject
    assert "Weekly Player" in html
    assert "4" in html
    assert "phase_weakness" not in html
    assert "Phase Weakness" in html or "phase weakness" in html.lower()


def test_send_weekly_summary_email_skips_when_not_configured(owner):
    summary = WeeklySummary(
        user_id=owner.id,
        email=owner.email,
        display_name="Weekly Player",
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
    )
    result = send_weekly_summary_email(owner, summary)
    assert result["status"] == "skipped"
    assert result["reason"] == "email_delivery_not_configured"


def test_scheduled_weekly_summary_dispatch_skips_when_disabled():
    with patch("app.tasks.retention_tasks.settings.WEEKLY_EMAIL_ENABLED", False):
        result = scheduled_weekly_summary_dispatch_task()
    assert result["status"] == "skipped"
    assert result["reason"] == "weekly_email_disabled"


def test_scheduled_weekly_summary_dispatch_fan_out(db, owner):
    with patch("app.tasks.retention_tasks.settings.WEEKLY_EMAIL_ENABLED", True), patch(
        "app.tasks.retention_tasks.settings.WEEKLY_EMAIL_MAX_USERS_PER_RUN",
        10,
    ), patch(
        "app.tasks.retention_tasks.settings.WEEKLY_EMAIL_STAGGER_SECONDS",
        0,
    ), patch(
        "app.tasks.retention_tasks.SessionLocal",
        return_value=db,
    ), patch(
        "app.tasks.retention_tasks.send_weekly_summary_task.apply_async",
    ) as apply_mock:
        result = scheduled_weekly_summary_dispatch_task()

    assert result["status"] == "dispatched"
    assert owner.id in result["user_ids"]
    apply_mock.assert_called_once_with(args=[owner.id], countdown=0)


def test_send_weekly_summary_task_skips_opted_out(db, owner):
    owner.notification_preferences = {"weekly_summary_enabled": False}
    db.commit()
    with patch(
        "app.tasks.retention_tasks.SessionLocal",
        return_value=db,
    ):
        result = send_weekly_summary_task(owner.id)
    assert result["status"] == "skipped"
    assert result["reason"] == "weekly_summary_disabled"
