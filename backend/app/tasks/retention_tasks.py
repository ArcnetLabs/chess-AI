"""Celery tasks for weekly summary email dispatch (P2-RT-02)."""
from __future__ import annotations

from typing import List

from loguru import logger

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.services.retention.email_delivery_service import (
    is_weekly_email_enabled,
    send_weekly_summary_email,
)
from app.services.retention.weekly_summary_service import build_weekly_summary


@celery_app.task(
    name="app.tasks.retention_tasks.scheduled_weekly_summary_dispatch_task",
)
def scheduled_weekly_summary_dispatch_task() -> dict:
    """
    Celery beat entry point: fan out per-user weekly summary tasks.

    Disabled unless ``WEEKLY_EMAIL_ENABLED`` is true in settings.
    """
    if not settings.WEEKLY_EMAIL_ENABLED:
        logger.debug("Weekly summary dispatch skipped: WEEKLY_EMAIL_ENABLED=false")
        return {"status": "skipped", "reason": "weekly_email_disabled", "users_dispatched": 0}

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
                .limit(settings.WEEKLY_EMAIL_MAX_USERS_PER_RUN)
                .all()
            )
        ]

        dispatched: List[int] = []
        for index, user_id in enumerate(user_ids):
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not is_weekly_email_enabled(user):
                continue

            send_weekly_summary_task.apply_async(
                args=[user_id],
                countdown=index * settings.WEEKLY_EMAIL_STAGGER_SECONDS,
            )
            dispatched.append(user_id)

        logger.info(f"Weekly summary dispatch sent {len(dispatched)} user tasks")
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
    name="app.tasks.retention_tasks.send_weekly_summary_task",
)
def send_weekly_summary_task(self, user_id: int) -> dict:
    """Build and send (or stub) the weekly summary email for one user."""
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

        if not is_weekly_email_enabled(user):
            return {
                "status": "skipped",
                "reason": "weekly_summary_disabled",
                "user_id": user_id,
            }

        summary = build_weekly_summary(db, user_id)
        if summary is None:
            return {
                "status": "skipped",
                "reason": "summary_unavailable",
                "user_id": user_id,
            }

        return send_weekly_summary_email(user, summary)
    except Exception as exc:
        logger.error(f"Weekly summary failed for user_id={user_id}: {exc}")
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
