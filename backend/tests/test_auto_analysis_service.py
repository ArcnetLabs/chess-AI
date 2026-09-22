"""Tests for P2-AA-01 post-sync auto-analysis queue."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.models.game import Game
from app.models.user import User
from app.services.analysis.auto_analysis_service import (
    AUTO_ANALYZE_PREF_KEY,
    is_auto_analyze_enabled,
    queue_new_games_for_analysis,
)


@pytest.fixture
def user(db):
    user = User(
        supabase_user_id="test-sub",
        chesscom_username="testplayer",
        analysis_preferences={},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_is_auto_analyze_enabled_defaults_true(user):
    assert is_auto_analyze_enabled(user) is True


def test_is_auto_analyze_enabled_respects_user_preference(user):
    user.analysis_preferences = {AUTO_ANALYZE_PREF_KEY: False}
    assert is_auto_analyze_enabled(user) is False


def test_is_auto_analyze_enabled_request_override_wins(user):
    user.analysis_preferences = {AUTO_ANALYZE_PREF_KEY: False}
    assert is_auto_analyze_enabled(user, request_override=True) is True


def test_queue_skips_when_disabled(db, user):
    user.analysis_preferences = {AUTO_ANALYZE_PREF_KEY: False}
    db.commit()

    result = queue_new_games_for_analysis(db, user, [1, 2, 3])

    assert result["status"] == "skipped"
    assert result["reason"] == "auto_analyze_disabled"
    assert result["games_queued"] == 0


def test_queue_skips_when_no_eligible_games(db, user):
    result = queue_new_games_for_analysis(db, user, [999])

    assert result["status"] == "skipped"
    assert result["reason"] == "no_eligible_games"


@patch("app.tasks.analysis_tasks.analyze_batch_games_task")
def test_queue_dispatches_batch_task(mock_batch_task, db, user):
    game = Game(
        user_id=user.id,
        chesscom_game_id="abc-123",
        pgn="1. e4 e5",
        is_analyzed=False,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    mock_task = MagicMock()
    mock_task.id = "celery-task-1"
    mock_batch_task.delay.return_value = mock_task

    result = queue_new_games_for_analysis(
        db,
        user,
        [game.id],
        source="test",
    )

    assert result["status"] == "queued"
    assert result["games_queued"] == 1
    assert result["task_id"] == "celery-task-1"
    # The job id is the store's own id, not the Celery task id: the job store
    # owns progress tracking (this assertion predated that refactor).
    assert result["job_id"]
    assert result["job_id"] != result["task_id"]
    mock_batch_task.delay.assert_called_once_with(
        [game.id], user.id, source="test", job_id=result["job_id"]
    )


@patch("app.tasks.analysis_tasks.analyze_batch_games_task")
def test_queue_skips_already_analyzed_games(mock_batch_task, db, user):
    game = Game(
        user_id=user.id,
        chesscom_game_id="done-123",
        pgn="1. e4 e5",
        is_analyzed=True,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    result = queue_new_games_for_analysis(db, user, [game.id])

    assert result["status"] == "skipped"
    assert result["reason"] == "no_eligible_games"
    mock_batch_task.delay.assert_not_called()


@patch("app.tasks.analysis_tasks.analyze_batch_games_task")
def test_queue_is_capped_at_max_games_per_analysis(mock_batch_task, db, user, monkeypatch):
    """Onboarding length is set by the queue cap, not by the import size.

    MAX_GAMES_PER_ANALYSIS used to bound only the date-based fetch, so the
    count-based onboarding path queued the whole library (199 games) whatever
    the setting said.
    """
    monkeypatch.setattr(settings, "MAX_GAMES_PER_ANALYSIS", 5, raising=False)

    mock_batch_task.delay.return_value = MagicMock(id="celery-task-cap")
    now = datetime.now(timezone.utc)
    ids = []
    for index in range(12):
        game = Game(
            user_id=user.id,
            chesscom_game_id=f"cap-{index}",
            pgn="1. e4 e5",
            is_analyzed=False,
            end_time=now - timedelta(days=index),
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        ids.append(game.id)

    result = queue_new_games_for_analysis(db, user, ids, source="test")

    assert result["status"] == "queued"
    assert result["games_queued"] == 5
    queued = mock_batch_task.delay.call_args[0][0]
    assert len(queued) == 5
    # Most recent first: the cap keeps the newest games.
    assert queued == ids[:5]


@patch("app.tasks.analysis_tasks.analyze_batch_games_task")
def test_queue_keeps_everything_when_cap_is_zero(mock_batch_task, db, user, monkeypatch):
    monkeypatch.setattr(settings, "MAX_GAMES_PER_ANALYSIS", 0, raising=False)
    mock_batch_task.delay.return_value = MagicMock(id="celery-task-nocap")

    ids = []
    for index in range(4):
        game = Game(
            user_id=user.id,
            chesscom_game_id=f"nocap-{index}",
            pgn="1. e4 e5",
            is_analyzed=False,
            end_time=datetime.now(timezone.utc) - timedelta(days=index),
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        ids.append(game.id)

    result = queue_new_games_for_analysis(db, user, ids, source="test")

    assert result["games_queued"] == 4
