"""Tests for P2-AA-05 game sync service and beat dispatch."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.services.games.game_sync_service import (
    determine_winner,
    import_chesscom_games,
    is_scheduled_sync_enabled,
    persist_chesscom_games,
)
from app.tasks.sync_tasks import scheduled_chesscom_sync_task


@pytest.fixture
def owner(db):
    user = User(
        supabase_user_id="sync-user",
        chesscom_username="player1",
        email="sync@example.com",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_determine_winner():
    assert determine_winner("win", "resigned") == "white"
    assert determine_winner("resigned", "win") == "black"
    assert determine_winner("stalemate", "stalemate") == "draw"
    assert determine_winner("timeout", "timeout") is None


def test_is_scheduled_sync_enabled_defaults_true(owner):
    assert is_scheduled_sync_enabled(owner) is True


def test_is_scheduled_sync_enabled_respects_preference(owner):
    owner.analysis_preferences = {"scheduled_sync_enabled": False}
    assert is_scheduled_sync_enabled(owner) is False


def test_persist_chesscom_games_skips_existing(db, owner):
    raw_games = [
        {
            "uuid": "game-1",
            "url": "https://chess.com/game/1",
            "time_class": "rapid",
            "time_control": "600+0",
            "rules": "chess",
            "white": {"username": "player1", "rating": 1500, "result": "win"},
            "black": {"username": "opponent1", "rating": 1490, "result": "resigned"},
            "pgn": "[Event \"Test\"]\n1. e4 1-0",
            "fen": "start",
            "end_time": 1710000000,
        }
    ]

    with patch(
        "app.services.games.game_sync_service.chesscom_api.parse_game_data",
        return_value={
            "chesscom_game_id": "game-1",
            "chesscom_url": "https://chess.com/game/1",
            "time_class": "rapid",
            "time_control": "600+0",
            "rules": "chess",
            "white_username": "player1",
            "black_username": "opponent1",
            "white_rating": 1500,
            "black_rating": 1490,
            "white_result": "win",
            "black_result": "resigned",
            "pgn": "1. e4",
            "fen": "fen",
            "start_time": None,
            "end_time": None,
        },
    ):
        added, updated, new_ids = persist_chesscom_games(db, owner, raw_games)
        assert added == 1
        assert updated == 0
        assert len(new_ids) == 1

        added2, updated2, new_ids2 = persist_chesscom_games(db, owner, raw_games)
        assert added2 == 0
        assert updated2 == 1
        assert new_ids2 == []


@pytest.mark.asyncio
async def test_import_chesscom_games_queues_analysis(db, owner):
    raw_games = [{"uuid": "game-2"}]

    with patch(
        "app.services.games.game_sync_service.chesscom_api.get_recent_games",
        new=AsyncMock(return_value=raw_games),
    ), patch(
        "app.services.games.game_sync_service.persist_chesscom_games",
        return_value=(2, 1, [10, 11]),
    ), patch(
        "app.services.games.game_sync_service.queue_new_games_for_analysis",
        return_value={"status": "queued", "games_queued": 2},
    ) as queue_mock:
        result = await import_chesscom_games(
            db,
            owner,
            days=7,
            source="scheduled_beat_sync",
        )

    assert result["status"] == "success"
    assert result["games_added"] == 2
    queue_mock.assert_called_once()


def test_scheduled_chesscom_sync_task_skips_when_beat_disabled():
    with patch("app.tasks.sync_tasks.settings.CELERY_BEAT_ENABLED", False):
        result = scheduled_chesscom_sync_task()
    assert result["status"] == "skipped"
    assert result["reason"] == "beat_disabled"


def test_scheduled_chesscom_sync_task_dispatches_enabled_users(db, owner):
    owner.analysis_preferences = {"scheduled_sync_enabled": True}
    db.commit()

    disabled = User(
        supabase_user_id="sync-user-2",
        chesscom_username="player2",
        email="sync2@example.com",
        analysis_preferences={"scheduled_sync_enabled": False},
    )
    db.add(disabled)
    db.commit()

    with patch("app.tasks.sync_tasks.settings.CELERY_BEAT_ENABLED", True), patch(
        "app.tasks.sync_tasks.settings.CHESSCOM_SCHEDULED_SYNC_MAX_USERS_PER_RUN",
        50,
    ), patch(
        "app.tasks.sync_tasks.settings.CHESSCOM_SCHEDULED_SYNC_STAGGER_SECONDS",
        0,
    ), patch(
        "app.tasks.sync_tasks.SessionLocal",
        return_value=db,
    ), patch(
        "app.tasks.sync_tasks.sync_user_games_task.apply_async",
    ) as apply_mock:
        result = scheduled_chesscom_sync_task()

    assert result["status"] == "dispatched"
    assert result["users_dispatched"] == 1
    assert owner.id in result["user_ids"]
    apply_mock.assert_called_once_with(args=[owner.id], countdown=0)
