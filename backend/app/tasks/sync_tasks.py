"""Celery tasks for scheduled Chess.com sync (P2-AA-05)."""
from __future__ import annotations

import asyncio
from typing import List

from loguru import logger

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.services.games.game_sync_service import (
    import_chesscom_games,
    is_scheduled_sync_enabled,
)
from app.services.integration.chesscom_api import ChessComAPIError, RateLimitExceeded


@celery_app.task(
    name="app.tasks.sync_tasks.scheduled_chesscom_sync_task",
)
def scheduled_chesscom_sync_task() -> dict:
    """
    Celery beat entry point: fan out per-user sync tasks.

    Disabled unless ``CELERY_BEAT_ENABLED`` is true in settings.
    """
    if not settings.CELERY_BEAT_ENABLED:
        logger.debug("Scheduled Chess.com sync skipped: CELERY_BEAT_ENABLED=false")
        return {"status": "skipped", "reason": "beat_disabled", "users_dispatched": 0}

    db = SessionLocal()
    try:
        user_ids: List[int] = [
            row[0]
            for row in (
                db.query(User.id)
                .filter(
                    User.is_active.is_(True),
                    User.chesscom_username.isnot(None),
                    User.chesscom_username != "",
                )
                .order_by(User.id.asc())
                .limit(settings.CHESSCOM_SCHEDULED_SYNC_MAX_USERS_PER_RUN)
                .all()
            )
        ]

        dispatched: List[int] = []
        for index, user_id in enumerate(user_ids):
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not is_scheduled_sync_enabled(user):
                continue

            sync_user_games_task.apply_async(
                args=[user_id],
                countdown=index * settings.CHESSCOM_SCHEDULED_SYNC_STAGGER_SECONDS,
            )
            dispatched.append(user_id)

        logger.info(f"Scheduled Chess.com sync dispatched {len(dispatched)} user tasks")
        return {
            "status": "dispatched",
            "users_dispatched": len(dispatched),
            "user_ids": dispatched,
        }
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name="app.tasks.sync_tasks.sync_user_games_task",
)
def sync_user_games_task(self, user_id: int) -> dict:
    """Sync recent Chess.com games for a single user."""
    db = SessionLocal()
    loop = asyncio.new_event_loop()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "failed", "reason": "user_not_found", "user_id": user_id}

        if not user.chesscom_username:
            return {
                "status": "skipped",
                "reason": "no_chesscom_username",
                "user_id": user_id,
            }

        if not is_scheduled_sync_enabled(user):
            return {
                "status": "skipped",
                "reason": "scheduled_sync_disabled",
                "user_id": user_id,
            }

        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            import_chesscom_games(
                db,
                user,
                days=settings.CHESSCOM_SCHEDULED_SYNC_DAYS,
                source="scheduled_beat_sync",
            )
        )
        result["user_id"] = user_id
        return result
    except RateLimitExceeded as exc:
        logger.warning(
            f"Chess.com rate limit for user_id={user_id}; "
            f"retry in {exc.retry_after}s"
        )
        raise self.retry(countdown=max(int(exc.retry_after), 30), exc=exc)
    except ChessComAPIError as exc:
        logger.error(f"Chess.com sync failed for user_id={user_id}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(exc),
            "retries": self.request.retries,
        }
    except Exception as exc:
        db.rollback()
        logger.error(f"Unexpected sync failure for user_id={user_id}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(exc),
            "retries": self.request.retries,
        }
    finally:
        loop.close()
        db.close()
