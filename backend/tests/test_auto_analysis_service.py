"""Tests for P2-AA-01 post-sync auto-analysis queue."""
from unittest.mock import MagicMock, patch

import pytest

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
    mock_batch_task.delay.assert_called_once_with([game.id], user.id)


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
