"""POST /analysis/{user_id}/analyze — no duplicate queueing.

The import path auto-queues the games it fetched, so a client that fetches and
then calls this endpoint used to queue the same games twice and pay for two full
engine passes over them.
"""

from datetime import datetime, timezone

from app.api import analysis as analysis_api
from app.models.game import Game
from app.models.user import User


def _user(db, email="dup@example.com") -> User:
    user = User(
        email=email,
        supabase_user_id=f"sub-{email}",
        connection_type="username_only",
        chesscom_username="dupuser",
        tier="free",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _game(db, user: User, index: int, *, analyzed: bool = False, pgn: str = "1. e4 e5") -> Game:
    game = Game(
        user_id=user.id,
        chesscom_game_id=f"dup-game-{user.id}-{index}",
        white_username="dupuser",
        black_username="opponent",
        pgn=pgn,
        is_analyzed=analyzed,
        end_time=datetime.now(timezone.utc),
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


class _StubStore:
    """Minimal job store stand-in recording what the endpoint queued."""

    def __init__(self, active=None):
        self.active = active
        self.created = []

    def get_active_job(self, user_id):
        return self.active

    def create_job(self, *, job_id, user_id, game_ids, source="manual"):
        self.created.append({"job_id": job_id, "game_ids": list(game_ids), "source": source})
        return {"job_id": job_id}


class _StubTask:
    id = "task-1"


async def _run(db, monkeypatch, store, user, **request_kwargs):
    monkeypatch.setattr(analysis_api, "get_analysis_job_store", lambda: store)
    monkeypatch.setattr(analysis_api.analyze_batch_games_task, "delay", lambda *a, **k: _StubTask())
    return await analysis_api.analyze_user_games(
        user_id=user.id,
        request=analysis_api.AnalysisRequest(mode="stockfish-only", **request_kwargs),
        current_user=user,
        db=db,
    )


class TestNoDuplicateQueueing:
    async def test_skips_games_already_covered_by_the_running_job(self, db, monkeypatch):
        user = _user(db)
        first = _game(db, user, 1)
        second = _game(db, user, 2)
        third = _game(db, user, 3)

        store = _StubStore(
            active={"job_id": "running-1", "status": "running", "game_ids": [first.id, second.id]}
        )
        result = await _run(db, monkeypatch, store, user)

        assert result["games_queued"] == 1
        assert result["skipped_already_queued"] == 2
        assert store.created[0]["game_ids"] == [third.id]

    async def test_returns_the_running_job_when_nothing_is_left(self, db, monkeypatch):
        user = _user(db)
        game = _game(db, user, 1)
        store = _StubStore(active={"job_id": "running-2", "status": "running", "game_ids": [game.id]})

        result = await _run(db, monkeypatch, store, user)

        assert result["games_queued"] == 0
        assert result["job_id"] == "running-2"
        assert result.get("already_running") is True
        assert store.created == []

    async def test_terminal_jobs_do_not_block_a_new_run(self, db, monkeypatch):
        user = _user(db)
        _game(db, user, 1)
        store = _StubStore(active={"job_id": "done-1", "status": "completed", "game_ids": [1]})

        result = await _run(db, monkeypatch, store, user)

        assert result["games_queued"] == 1
        assert len(store.created) == 1

    async def test_force_reanalysis_ignores_the_running_job(self, db, monkeypatch):
        user = _user(db)
        game = _game(db, user, 1)
        store = _StubStore(active={"job_id": "running-3", "status": "running", "game_ids": [game.id]})

        result = await _run(db, monkeypatch, store, user, force_reanalysis=True)

        assert result["games_queued"] == 1
        assert len(store.created) == 1
