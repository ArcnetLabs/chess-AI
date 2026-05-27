"""
Celery task for manual and scheduled player profile snapshot builds.

P1-PP-02 adds debounced scheduling from pattern detection; this module provides
the core ``build_profile_task`` consumed by the profile API (P1-PP-03).
"""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.profiles.profile_builder import build_player_profile


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    name="app.tasks.profile_tasks.build_profile_task",
)
def build_profile_task(self, user_id: int):
    """
    Celery task: build and persist an append-only PlayerProfile snapshot.

    Idempotent — safe to retry; versioning prevents duplicate snapshot rows
    for the same logical build (each run creates a new version).
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting profile build for user_id={user_id}")
        profile = build_player_profile(db, user_id)
        if profile is None:
            logger.info(
                f"Profile build skipped for user_id={user_id} "
                f"(insufficient games or user not found)"
            )
            return {
                "status": "skipped",
                "user_id": user_id,
                "profile_id": None,
                "profile_version": None,
            }

        logger.info(
            f"Profile build complete user_id={user_id} "
            f"version={profile.profile_version} id={profile.id}"
        )
        return {
            "status": "success",
            "user_id": user_id,
            "profile_id": profile.id,
            "profile_version": profile.profile_version,
            "games_analyzed_count": profile.games_analyzed_count,
            "patterns_detected_count": profile.patterns_detected_count,
        }
    except Exception as exc:
        db.rollback()
        logger.error(f"Profile build failed for user_id={user_id}: {exc}")
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
