"""Tests for analysis pipeline diagnostics (self-diagnosing pipeline-status)."""
import asyncio

import pytest

from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.analysis.analysis_job_store import AnalysisJobStore
from app.services.analysis.pipeline_diagnostics import collect_pipeline_status


@pytest.fixture
def user(db):
    user = User(supabase_user_id="diag-sub", chesscom_username="gh_wilder")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _run(db, user, **kwargs):
    store = AnalysisJobStore(redis=None, ttl_seconds=3600)
    return asyncio.run(
        collect_pipeline_status(db, user, job_store=store, **kwargs)
    )


async def _engine_ok():
    return {"available": True, "initialized": True, "path": "stockfish/stockfish"}


async def _engine_down():
    return {"available": False, "error": "Stockfish binary not found"}


async def _workers_none():
    return []


async def _workers_one():
    return ["celery@worker-1"]


def _add_game(db, user, *, pgn="1. e4 e5", analyzed=False):
    game = Game(
        user_id=user.id,
        chesscom_game_id=f"g-{pgn[:4]}-{analyzed}",
        pgn=pgn,
        is_analyzed=analyzed,
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def test_diagnosis_no_games(db, user):
    result = _run(db, user, engine_probe=_engine_ok, worker_probe=_workers_one)
    assert result["total_games_fetched"] == 0
    assert result["healthy"] is False
    assert "No games fetched" in result["diagnosis"]


def test_diagnosis_engine_unavailable(db, user):
    _add_game(db, user)
    result = _run(db, user, engine_probe=_engine_down, worker_probe=_workers_one)
    assert result["engine"]["available"] is False
    assert "UNAVAILABLE" in result["diagnosis"]


def test_diagnosis_no_worker(db, user):
    _add_game(db, user)
    result = _run(db, user, engine_probe=_engine_ok, worker_probe=_workers_none)
    assert result["workers_online"] == 0
    assert "No Celery worker" in result["diagnosis"]


def test_diagnosis_healthy_when_analysis_present(db, user):
    game = _add_game(db, user, analyzed=True)
    db.add(GameAnalysis(game_id=game.id, user_acpl=25.0, accuracy_percentage=90.0))
    db.commit()

    result = _run(db, user, engine_probe=_engine_ok, worker_probe=_workers_one)
    assert result["game_analysis_rows"] == 1
    assert result["games_flagged_analyzed"] == 1
    assert result["healthy"] is True
    assert "Healthy" in result["diagnosis"]


def test_diagnosis_surfaces_failed_job_error(db, user):
    game = _add_game(db, user)
    store = AnalysisJobStore(redis=None, ttl_seconds=3600)
    store.create_job(job_id="job-x", user_id=user.id, game_ids=[game.id], source="manual")
    store.mark_game_failed("job-x", game.id, error="Stockfish binary not found")

    result = asyncio.run(
        collect_pipeline_status(
            db, user, job_store=store, engine_probe=_engine_ok, worker_probe=_workers_one
        )
    )
    assert result["recent_job"]["failed_games"] == 1
    assert result["recent_job"]["last_error"] == "Stockfish binary not found"
    assert "FAILED" in result["diagnosis"]
