"""Tests for profile Celery task wiring (P1-PP-02)."""

from unittest.mock import MagicMock, patch

import pytest

from app.tasks.pattern_tasks import detect_patterns_task
from app.tasks.profile_tasks import (
    PROFILE_BUILD_DEBOUNCE_KEY_PREFIX,
    build_profile_task,
    schedule_profile_build_for_user,
)


class TestScheduleProfileBuild:
    def test_schedules_without_redis(self):
        mock_apply = MagicMock()
        with patch("app.tasks.profile_tasks.redis_client", None), patch(
            "app.tasks.profile_tasks.build_profile_task.apply_async",
            mock_apply,
        ):
            scheduled = schedule_profile_build_for_user(42)

        assert scheduled is True
        mock_apply.assert_called_once_with(args=[42], countdown=60)

    def test_debounce_skips_when_key_exists(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = False
        mock_apply = MagicMock()

        with patch("app.tasks.profile_tasks.redis_client", mock_redis), patch(
            "app.tasks.profile_tasks.build_profile_task.apply_async",
            mock_apply,
        ):
            scheduled = schedule_profile_build_for_user(7)

        assert scheduled is False
        mock_redis.set.assert_called_once_with(
            f"{PROFILE_BUILD_DEBOUNCE_KEY_PREFIX}:7",
            "1",
            nx=True,
            ex=120,
        )
        mock_apply.assert_not_called()

    def test_debounce_schedules_when_key_missing(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        mock_apply = MagicMock()

        with patch("app.tasks.profile_tasks.redis_client", mock_redis), patch(
            "app.tasks.profile_tasks.build_profile_task.apply_async",
            mock_apply,
        ):
            scheduled = schedule_profile_build_for_user(7, countdown=45)

        assert scheduled is True
        mock_apply.assert_called_once_with(args=[7], countdown=45)


class TestBuildProfileTask:
    def test_calls_build_player_profile_success(self):
        mock_profile = MagicMock()
        mock_profile.id = 101
        mock_profile.profile_version = 2
        mock_profile.games_analyzed_count = 15
        mock_profile.patterns_detected_count = 4

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.return_value = mock_db

        with patch("app.tasks.profile_tasks.SessionLocal", mock_session), patch(
            "app.tasks.profile_tasks.build_player_profile",
            return_value=mock_profile,
        ) as mock_build:
            result = build_profile_task.run(99)

        mock_build.assert_called_once_with(mock_db, 99)
        mock_db.close.assert_called_once()
        assert result["status"] == "success"
        assert result["profile_id"] == 101
        assert result["profile_version"] == 2
        assert result["games_analyzed_count"] == 15
        assert result["patterns_detected_count"] == 4

    def test_skipped_when_builder_returns_none(self):
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.return_value = mock_db

        with patch("app.tasks.profile_tasks.SessionLocal", mock_session), patch(
            "app.tasks.profile_tasks.build_player_profile",
            return_value=None,
        ) as mock_build:
            result = build_profile_task.run(5)

        mock_build.assert_called_once_with(mock_db, 5)
        assert result["status"] == "skipped"
        assert result["profile_id"] is None


class TestPatternTaskHook:
    def test_successful_pattern_detection_schedules_profile_build(self):
        mock_result = MagicMock()
        mock_result.pattern_count = 3
        mock_result.games_considered = 12

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.return_value = mock_db

        with patch("app.tasks.pattern_tasks.SessionLocal", mock_session), patch(
            "app.tasks.pattern_tasks.run_pattern_detection",
            return_value=mock_result,
        ), patch(
            "app.tasks.pattern_tasks.schedule_profile_build_for_user",
        ) as mock_schedule:
            result = detect_patterns_task.run(88)

        assert result["status"] == "success"
        mock_schedule.assert_called_once_with(88)
