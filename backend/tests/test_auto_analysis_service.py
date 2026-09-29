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
def test_queue_skips_games_with_no_moves(mock_batch_task, db, user):
    """A headers-only game must not take a slot in the analysis window.

    This is the "49 games analyzed instead of 50" class: the queue counted the
    game, the engine found no moves, and the run reported one game short with
    no explanation on screen.
    """
    mock_batch_task.delay.return_value = MagicMock(id="celery-task-nomoves")

    playable = Game(
        user_id=user.id,
        chesscom_game_id="playable-1",
        pgn="1. e4 e5 2. Nf3 Nc6 1-0",
        is_analyzed=False,
        end_time=datetime.now(timezone.utc),
    )
    aborted = Game(
        user_id=user.id,
        chesscom_game_id="aborted-1",
        pgn=(
            '[Event "Live Chess"]\n'
            '[White "GH_Wilder"]\n'
            '[Black "000ZAKARIA000"]\n'
            '[Result "0-1"]\n'
            '[CurrentPosition "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]\n'
        ),
        is_analyzed=False,
        end_time=datetime.now(timezone.utc),
    )
    db.add_all([playable, aborted])
    db.commit()
    db.refresh(playable)
    db.refresh(aborted)

    result = queue_new_games_for_analysis(
        db, user, [playable.id, aborted.id], source="test"
    )

    assert result["status"] == "queued"
    assert result["games_queued"] == 1
    assert result["games_skipped_no_moves"] == 1
    mock_batch_task.delay.assert_called_once_with(
        [playable.id], user.id, source="test", job_id=result["job_id"]
    )


@patch("app.tasks.analysis_tasks.analyze_batch_games_task")
def test_queue_skips_a_game_the_player_never_moved_in(mock_batch_task, db, user):
    """Game 2750: one ply, played by the opponent.

    The player had Black in a game abandoned after ``1. d4``, so there is no
    move of theirs to analyze. It was queued anyway, scored 0.0 ACPL / 99.0%
    accuracy, and counted as one of the 50 analysed games.
    """
    mock_batch_task.delay.return_value = MagicMock(id="celery-task-oneply")

    abandoned = Game(
        user_id=user.id,
        chesscom_game_id="one-ply-abandoned",
        white_username="FranckRE",
        black_username="testplayer",
        pgn="1. d4 1-0",
        is_analyzed=False,
        end_time=datetime.now(timezone.utc),
    )
    db.add(abandoned)
    db.commit()
    db.refresh(abandoned)

    result = queue_new_games_for_analysis(db, user, [abandoned.id], source="test")

    assert result["status"] == "skipped"
    assert result["reason"] == "no_eligible_games"
    assert result["games_queued"] == 0
    assert result["games_skipped_no_moves"] == 1
    mock_batch_task.delay.assert_not_called()


@patch("app.tasks.analysis_tasks.analyze_batch_games_task")
def test_queue_keeps_a_one_ply_game_the_player_did_move_in(mock_batch_task, db, user):
    """The same single ply, seen from White's side, is a real move to score."""
    mock_batch_task.delay.return_value = MagicMock(id="celery-task-oneply-white")

    game = Game(
        user_id=user.id,
        chesscom_game_id="one-ply-white",
        white_username="testplayer",
        black_username="FranckRE",
        pgn="1. d4 1-0",
        is_analyzed=False,
        end_time=datetime.now(timezone.utc),
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    result = queue_new_games_for_analysis(db, user, [game.id], source="test")

    assert result["status"] == "queued"
    assert result["games_queued"] == 1
    assert result["games_skipped_no_moves"] == 0


@patch("app.tasks.analysis_tasks.analyze_batch_games_task")
def test_queue_reports_zero_skips_when_every_game_has_moves(mock_batch_task, db, user):
    mock_batch_task.delay.return_value = MagicMock(id="celery-task-allgood")
    game = Game(
        user_id=user.id,
        chesscom_game_id="all-good",
        pgn="1. e4 e5 1-0",
        is_analyzed=False,
        end_time=datetime.now(timezone.utc),
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    result = queue_new_games_for_analysis(db, user, [game.id], source="test")

    assert result["games_queued"] == 1
    assert result["games_skipped_no_moves"] == 0


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
