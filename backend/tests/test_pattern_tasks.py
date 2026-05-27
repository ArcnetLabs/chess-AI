"""Tests for pattern Celery task wiring (P1-PR-05)."""

from unittest.mock import MagicMock, patch

import pytest

from app.tasks.analysis_tasks import analyze_game_task
from app.tasks.pattern_tasks import (
    PATTERN_DEBOUNCE_KEY_PREFIX,
    detect_patterns_task,
    schedule_pattern_detection_for_user,
)


class TestSchedulePatternDetection:
    def test_schedules_without_redis(self):
        mock_apply = MagicMock()
        with patch("app.tasks.pattern_tasks.redis_client", None), patch(
            "app.tasks.pattern_tasks.detect_patterns_task.apply_async",
            mock_apply,
        ):
            scheduled = schedule_pattern_detection_for_user(42)

        assert scheduled is True
        mock_apply.assert_called_once_with(args=[42], countdown=60)

    def test_debounce_skips_when_key_exists(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = False
        mock_apply = MagicMock()

        with patch("app.tasks.pattern_tasks.redis_client", mock_redis), patch(
            "app.tasks.pattern_tasks.detect_patterns_task.apply_async",
            mock_apply,
        ):
            scheduled = schedule_pattern_detection_for_user(7)

        assert scheduled is False
        mock_redis.set.assert_called_once_with(
            f"{PATTERN_DEBOUNCE_KEY_PREFIX}:7",
            "1",
            nx=True,
            ex=120,
        )
        mock_apply.assert_not_called()

    def test_debounce_schedules_when_key_missing(self):
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        mock_apply = MagicMock()

        with patch("app.tasks.pattern_tasks.redis_client", mock_redis), patch(
            "app.tasks.pattern_tasks.detect_patterns_task.apply_async",
            mock_apply,
        ):
            scheduled = schedule_pattern_detection_for_user(7, countdown=45)

        assert scheduled is True
        mock_apply.assert_called_once_with(args=[7], countdown=45)


class TestDetectPatternsTask:
    def test_calls_run_pattern_detection_with_persist(self):
        mock_result = MagicMock()
        mock_result.pattern_count = 2
        mock_result.games_considered = 10

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.return_value = mock_db

        with patch("app.tasks.pattern_tasks.SessionLocal", mock_session), patch(
            "app.tasks.pattern_tasks.run_pattern_detection",
            return_value=mock_result,
        ) as mock_run, patch(
            "app.tasks.pattern_tasks.schedule_profile_build_for_user",
        ):
            result = detect_patterns_task.run(99)

        mock_run.assert_called_once_with(mock_db, 99, persist=True)
        mock_db.close.assert_called_once()
        assert result["status"] == "success"
        assert result["pattern_count"] == 2
        assert result["games_considered"] == 10


class TestAnalysisTaskHook:
    def test_successful_analysis_schedules_pattern_detection(self):
        import asyncio

        real_loop = asyncio.new_event_loop()
        try:
            with patch(
                "app.tasks.analysis_tasks.schedule_pattern_detection_for_user"
            ) as mock_schedule, patch(
                "app.tasks.analysis_tasks.SessionLocal"
            ) as mock_session_local, patch(
                "app.tasks.analysis_tasks.analyze_game_for_user"
            ), patch(
                "app.tasks.analysis_tasks.persist_game_analysis"
            ), patch(
                "asyncio.new_event_loop", return_value=real_loop
            ), patch.object(
                real_loop, "run_until_complete"
            ) as mock_run_until_complete:
                mock_db = MagicMock()
                mock_session_local.return_value = mock_db

                mock_game = MagicMock()
                mock_game.pgn = "[Event \"Test\"]\n1. e4 e5 2. Nf3 *"
                mock_user = MagicMock()
                mock_db.query.return_value.filter.return_value.first.side_effect = [
                    mock_game,
                    mock_user,
                    None,
                ]

                mock_result = MagicMock()
                mock_result.user_acpl = 25.0
                mock_result.accuracy_percentage = 85.0
                mock_result.blunders = 0
                mock_result.mistakes = 1
                mock_result.inaccuracies = 2
                mock_run_until_complete.return_value = mock_result

                response = analyze_game_task.run(1, 5)
        finally:
            real_loop.close()

        assert response["status"] == "success"
        mock_schedule.assert_called_once_with(5)
