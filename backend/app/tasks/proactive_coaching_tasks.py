"""Celery tasks for proactive coaching weekly digest (P3-PC-01)."""
from __future__ import annotations

from typing import List

from loguru import logger

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.services.retention.email_delivery_service import (
    is_weekly_digest_enabled,
    send_weekly_digest_email,
)
from app.services.notifications.notification_service import (
    NOTIFICATION_TYPE_WEEKLY_DIGEST,
    create_notification,
)
from app.services.retention.weekly_digest_service import (
    build_weekly_digest,
    render_weekly_digest_email,
)


@celery_app.task(
    name="app.tasks.proactive_coaching_tasks.scheduled_weekly_digest_dispatch_task",
)
def scheduled_weekly_digest_dispatch_task() -> dict:
    """
    Celery beat entry point: fan out per-user weekly digest tasks.

    Disabled unless ``WEEKLY_DIGEST_ENABLED`` is true in settings.
    """
    if not settings.WEEKLY_DIGEST_ENABLED:
        logger.debug("Weekly digest dispatch skipped: WEEKLY_DIGEST_ENABLED=false")
        return {
            "status": "skipped",
            "reason": "weekly_digest_disabled",
            "users_dispatched": 0,
        }

    db = SessionLocal()
    try:
        user_ids: List[int] = [
            row[0]
            for row in (
                db.query(User.id)
                .filter(
                    User.is_active.is_(True),
                    User.email.isnot(None),
                    User.email != "",
                )
                .order_by(User.id.asc())
                .limit(settings.WEEKLY_DIGEST_MAX_USERS_PER_RUN)
                .all()
            )
        ]

        dispatched: List[int] = []
        for index, user_id in enumerate(user_ids):
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not is_weekly_digest_enabled(user):
                continue

            send_weekly_digest_task.apply_async(
                args=[user_id],
                countdown=index * settings.WEEKLY_DIGEST_STAGGER_SECONDS,
            )
            dispatched.append(user_id)

        logger.info(f"Weekly digest dispatch sent {len(dispatched)} user tasks")
        return {
            "status": "dispatched",
            "users_dispatched": len(dispatched),
            "user_ids": dispatched,
        }
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="app.tasks.proactive_coaching_tasks.send_weekly_digest_task",
)
def send_weekly_digest_task(self, user_id: int) -> dict:
    """Build and send (or stub) the weekly coaching digest for one user."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "failed", "reason": "user_not_found", "user_id": user_id}

        if not user.email:
            return {
                "status": "skipped",
                "reason": "no_email",
                "user_id": user_id,
            }

        if not is_weekly_digest_enabled(user):
            return {
                "status": "skipped",
                "reason": "weekly_digest_disabled",
                "user_id": user_id,
            }

        digest = build_weekly_digest(db, user_id)
        if digest is None:
            return {
                "status": "skipped",
                "reason": "digest_unavailable",
                "user_id": user_id,
            }

        result = send_weekly_digest_email(user, digest)
        if result.get("status") in ("skipped", "sent"):
            subject, _ = render_weekly_digest_email(digest)
            create_notification(
                db,
                user_id,
                NOTIFICATION_TYPE_WEEKLY_DIGEST,
                title=subject,
                body=digest.coaching_tip,
                payload={
                    "period_start": digest.period_start.isoformat(),
                    "period_end": digest.period_end.isoformat(),
                    "games_played": digest.games_played,
                    "drills_completed_week": digest.drills_completed_week,
                    "email_status": result.get("status"),
                    "email_reason": result.get("reason"),
                },
            )
        return result
    except Exception as exc:
        logger.error(f"Weekly digest failed for user_id={user_id}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(exc),
            "retries": self.request.retries,
        }
    finally:
        db.close()
