"""Post-sync auto-analysis queue (P2-AA-01).

When games are imported from Chess.com, optionally queue Stockfish analysis
via Celery without requiring a separate manual analyze call.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.user import User

AUTO_ANALYZE_PREF_KEY = "auto_analyze_on_sync"
DEFAULT_AUTO_ANALYZE = True


def is_auto_analyze_enabled(
    user: User,
    request_override: Optional[bool] = None,
) -> bool:
    """Return whether newly synced games should be queued for analysis."""
    if request_override is not None:
        return request_override

    prefs = user.analysis_preferences or {}
    return bool(prefs.get(AUTO_ANALYZE_PREF_KEY, DEFAULT_AUTO_ANALYZE))


def queue_new_games_for_analysis(
    db: Session,
    user: User,
    game_ids: Iterable[int],
    *,
    source: str = "sync",
    request_override: Optional[bool] = None,
) -> dict:
    """Queue Celery batch analysis for unanalyzed synced games that have PGN."""
    if not is_auto_analyze_enabled(user, request_override):
        logger.info(
            f"Auto-analysis skipped for user {user.id} ({source}): preference disabled"
        )
        return {
            "status": "skipped",
            "reason": "auto_analyze_disabled",
            "games_queued": 0,
        }

    ids: List[int] = [game_id for game_id in game_ids if game_id]
    if not ids:
        return {
            "status": "skipped",
            "reason": "no_games",
            "games_queued": 0,
        }

    eligible_ids = [
        row[0]
        for row in db.query(Game.id)
        .filter(
            Game.id.in_(ids),
            Game.user_id == user.id,
            Game.is_analyzed.is_(False),
            Game.pgn.isnot(None),
            Game.pgn != "",
        )
        .all()
    ]

    if not eligible_ids:
        return {
            "status": "skipped",
            "reason": "no_eligible_games",
            "games_queued": 0,
        }

    from app.tasks.analysis_tasks import analyze_batch_games_task

    task = analyze_batch_games_task.delay(eligible_ids, user.id)
    logger.info(
        f"Auto-queued {len(eligible_ids)} games for analysis "
        f"(user={user.id}, source={source}, task={task.id})"
    )

    return {
        "status": "queued",
        "games_queued": len(eligible_ids),
        "task_id": task.id,
    }
