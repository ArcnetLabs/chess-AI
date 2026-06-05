"""Analysis pipeline diagnostics.

Produces a single, self-explaining snapshot of the Chess.com sync -> Stockfish
(Celery) -> ``game_analyses`` -> dashboard pipeline so an empty-KPI dashboard can
be diagnosed without reading Render worker logs.

The dashboard KPIs are aggregated from ``game_analyses`` rows, which are only
written when the Celery worker successfully runs Stockfish on a game's PGN. When
KPIs are empty the failure is almost always one of:

* Stockfish binary missing / not executable on the worker, or
* no Celery worker consuming the ``analysis`` queue, or
* every queued task failed.

This module surfaces exactly which of those is the case.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Game, GameAnalysis, User
from app.services.engine.engine_pool import check_engine_health
from app.services.analysis.analysis_job_store import (
    AnalysisJobStore,
    get_analysis_job_store,
)

EngineProbe = Callable[[], Awaitable[Dict[str, Any]]]
WorkerProbe = Callable[[], Awaitable[List[str]]]


async def ping_analysis_workers(timeout: float = 1.0) -> List[str]:
    """Return the hostnames of live Celery workers, or ``[]`` if none respond.

    A bounded broadcast ping — the single clearest signal for "is anything
    consuming the analysis queue?". Runs in a thread so the blocking Celery
    control call never stalls the event loop.
    """
    try:
        from app.celery_app import celery_app

        loop = asyncio.get_running_loop()
        replies = await loop.run_in_executor(
            None, lambda: celery_app.control.ping(timeout=timeout)
        )
        if not replies:
            return []
        return [host for reply in replies for host in reply.keys()]
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.warning(f"Celery worker ping failed: {exc}")
        return []


def _diagnose(
    *,
    total_games: int,
    games_with_pgn: int,
    games_analyzed: int,
    analysis_rows: int,
    engine: Dict[str, Any],
    workers_online: int,
    recent_job: Optional[Dict[str, Any]],
) -> str:
    """Human-readable verdict on where the pipeline stands (or breaks)."""
    if total_games == 0:
        return "No games fetched yet — run a Chess.com sync first."
    if games_with_pgn == 0:
        return (
            "Games fetched but none have a PGN stored — sync did not capture move "
            "data, so there is nothing for Stockfish to analyze."
        )
    if analysis_rows > 0 and games_analyzed > 0:
        return "Healthy — Stockfish analysis present; dashboard KPIs should populate."
    if not engine.get("available", False):
        return (
            "Stockfish engine is UNAVAILABLE on the API service "
            f"({engine.get('error', 'unknown error')}). The Celery worker most "
            "likely cannot run analysis either — verify render_install_stockfish.sh "
            "ran in the worker build and STOCKFISH_PATH is correct."
        )
    if workers_online == 0:
        return (
            "No Celery worker is consuming the 'analysis' queue — the "
            "chess-insight-celery worker is down or cannot reach Redis. Queued "
            "analysis tasks will never run, so game_analyses stays empty."
        )
    if recent_job and int(recent_job.get("failed_games", 0)) > 0:
        return (
            "Analysis tasks FAILED on the worker: "
            f"{recent_job.get('last_error') or 'see worker logs'}. "
            "Fix the worker error and re-run Analyze."
        )
    if recent_job and recent_job.get("status") in ("pending", "running"):
        completed = int(recent_job.get("completed_games", 0))
        total = int(recent_job.get("total_games", 0))
        return f"Analysis in progress — {completed}/{total} games complete."
    return (
        "Games are fetched and the engine looks healthy, but no analysis exists "
        "yet — POST /analyze to queue Stockfish analysis and confirm the worker "
        "processes it."
    )


async def collect_pipeline_status(
    db: Session,
    user: User,
    *,
    job_store: Optional[AnalysisJobStore] = None,
    engine_probe: EngineProbe = check_engine_health,
    worker_probe: WorkerProbe = ping_analysis_workers,
) -> Dict[str, Any]:
    """Assemble a debug-friendly snapshot of the analysis pipeline for ``user``.

    Probes (engine/worker) are injectable so tests can run without Stockfish or a
    live Celery worker.
    """
    user_id = user.id
    store = job_store or get_analysis_job_store()

    total_games = (
        db.query(func.count(Game.id)).filter(Game.user_id == user_id).scalar() or 0
    )
    games_with_pgn = (
        db.query(func.count(Game.id))
        .filter(Game.user_id == user_id, Game.pgn.isnot(None), Game.pgn != "")
        .scalar()
        or 0
    )
    games_analyzed = (
        db.query(func.count(Game.id))
        .filter(Game.user_id == user_id, Game.is_analyzed.is_(True))
        .scalar()
        or 0
    )
    analysis_rows = (
        db.query(func.count(GameAnalysis.id))
        .join(Game, GameAnalysis.game_id == Game.id)
        .filter(Game.user_id == user_id)
        .scalar()
        or 0
    )

    engine = await engine_probe()
    workers = await worker_probe()

    # Last job survives terminal status, so a failed run's reason stays visible
    # after the active pointer is cleared.
    job = store.get_last_job(user_id)
    recent_job = None
    if job:
        recent_job = {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "total_games": job.get("total_games"),
            "completed_games": job.get("completed_games"),
            "failed_games": job.get("failed_games"),
            "failed_game_ids": list(job.get("failed_game_ids", [])),
            "current_game_id": job.get("current_game_id"),
            "last_error": job.get("last_error"),
        }

    diagnosis = _diagnose(
        total_games=int(total_games),
        games_with_pgn=int(games_with_pgn),
        games_analyzed=int(games_analyzed),
        analysis_rows=int(analysis_rows),
        engine=engine,
        workers_online=len(workers),
        recent_job=recent_job,
    )

    return {
        "chesscom_username": user.chesscom_username,
        "total_games_fetched": int(total_games),
        "games_with_pgn": int(games_with_pgn),
        "games_flagged_analyzed": int(games_analyzed),
        "game_analysis_rows": int(analysis_rows),
        "engine": engine,
        "workers_online": len(workers),
        "worker_hosts": workers,
        "recent_job": recent_job,
        "pipeline": {
            "sync": "Chess.com API -> games table (PGN + metadata only)",
            "analyze": "Celery worker runs Stockfish on each PGN -> game_analyses table",
            "dashboard": "Summary API aggregates game_analyses (not Chess.com review data)",
        },
        "diagnosis": diagnosis,
        "healthy": int(analysis_rows) > 0 and int(games_analyzed) > 0,
    }
