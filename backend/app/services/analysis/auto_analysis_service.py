"""Post-sync auto-analysis queue (P2-AA-01).

When games are imported from Chess.com, optionally queue Stockfish analysis
via Celery without requiring a separate manual analyze call.
"""
from __future__ import annotations

from typing import Iterable, List, Optional
from uuid import uuid4

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.game import Game
from app.models.user import User
from app.services.analysis.analysis_job_store import get_analysis_job_store
from app.services.analysis.analysis_service import user_color_from_usernames
from app.services.analysis.pgn_preflight import has_analyzable_moves

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
            "games_skipped_no_moves": 0,
        }

    ids: List[int] = [game_id for game_id in game_ids if game_id]
    if not ids:
        return {
            "status": "skipped",
            "reason": "no_games",
            "games_queued": 0,
            "games_skipped_no_moves": 0,
        }

    eligible_rows = (
        db.query(Game.id, Game.pgn, Game.white_username)
        .filter(
            Game.id.in_(ids),
            Game.user_id == user.id,
            Game.is_analyzed.is_(False),
            Game.pgn.isnot(None),
            Game.pgn != "",
        )
        .order_by(Game.end_time.desc())
        .all()
    )

    # Chess.com keeps a row for games that never produced a move (aborted
    # tournament pairings): headers only, no movetext. They cannot be analyzed,
    # and the engine pass fails them deterministically — which is how a
    # 50-game window reported "49 games analyzed" with nothing on screen to
    # explain the missing game. Drop them here and report the count so the UI
    # can say so out loud.
    #
    # A one-ply aborted game the player had Black in is the same problem wearing
    # a different hat: there is movetext, but none of it is theirs. Scoring it
    # stored 0.0 ACPL / 99.0% accuracy for a game they never moved in (game
    # 2750), so the check is colour-aware.
    eligible_ids: List[int] = []
    no_move_ids: List[int] = []
    for game_id, pgn, white_username in eligible_rows:
        user_color = user_color_from_usernames(white_username, user.chesscom_username)
        if has_analyzable_moves(pgn, user_color):
            eligible_ids.append(game_id)
        else:
            no_move_ids.append(game_id)

    if no_move_ids:
        logger.info(
            f"Auto-analysis skipped {len(no_move_ids)} game(s) with no moves "
            f"for user {user.id} ({source}): {no_move_ids[:10]}"
        )

    # Onboarding duration is decided here, not by the import: the fetch keeps the
    # full library for Insights and the coach, while the bounded engine pass is
    # what the user waits for. MAX_GAMES_PER_ANALYSIS previously bounded only the
    # date-based fetch, so the count-based onboarding path queued the whole
    # library (199 games, ~18 minutes) regardless of the setting.
    cap = int(getattr(settings, "MAX_GAMES_PER_ANALYSIS", 0) or 0)
    if cap > 0 and len(eligible_ids) > cap:
        logger.info(
            f"Auto-analysis capped for user {user.id} ({source}): "
            f"{len(eligible_ids)} eligible, queueing the {cap} most recent"
        )
        eligible_ids = eligible_ids[:cap]

    if not eligible_ids:
        return {
            "status": "skipped",
            "reason": "no_eligible_games",
            "games_queued": 0,
            "games_skipped_no_moves": len(no_move_ids),
        }

    from app.tasks.analysis_tasks import analyze_batch_games_task

    job_store = get_analysis_job_store()
    job_id = str(uuid4())
    job_store.create_job(
        job_id=job_id,
        user_id=user.id,
        game_ids=eligible_ids,
        source=source,
    )
    task = analyze_batch_games_task.delay(
        eligible_ids,
        user.id,
        source=source,
        job_id=job_id,
    )
    logger.info(
        f"Auto-queued {len(eligible_ids)} games for analysis "
        f"(user={user.id}, source={source}, job={job_id}, celery={task.id})"
    )

    return {
        "status": "queued",
        "games_queued": len(eligible_ids),
        "games_skipped_no_moves": len(no_move_ids),
        "task_id": task.id,
        "job_id": job_id,
    }
