"""
Celery tasks for debounced player profile snapshots after pattern detection.

Debouncing strategy (P1-PP-02):
- ``detect_patterns_task`` calls :func:`schedule_profile_build_for_user` on success.
- Redis SET NX ensures at most one pending profile job per user within the debounce
  window, so rapid pattern reruns queue one delayed build instead of many.
- Without Redis (local dev), each call enqueues directly with countdown.
"""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal, redis_client
from app.services.profiles.profile_builder import build_player_profile

PROFILE_BUILD_DEBOUNCE_KEY_PREFIX = "profile_build_scheduled"
PROFILE_BUILD_DEBOUNCE_TTL_SECONDS = 120
PROFILE_BUILD_DEBOUNCE_COUNTDOWN_SECONDS = 60


def schedule_profile_build_for_user(
    user_id: int,
    *,
    countdown: int = PROFILE_BUILD_DEBOUNCE_COUNTDOWN_SECONDS,
) -> bool:
    """
    Enqueue profile build for a user, debounced per user_id.

    Returns True when a new Celery task was scheduled, False when suppressed
    by an active debounce key (another run is already pending).
    """
    if redis_client is None:
        build_profile_task.apply_async(args=[user_id], countdown=countdown)
        logger.debug(
            f"Scheduled profile build for user_id={user_id} "
            f"(no Redis debounce, countdown={countdown}s)"
        )
        return True

    debounce_key = f"{PROFILE_BUILD_DEBOUNCE_KEY_PREFIX}:{user_id}"
    if not redis_client.set(debounce_key, "1", nx=True, ex=PROFILE_BUILD_DEBOUNCE_TTL_SECONDS):
        logger.debug(
            f"Profile build debounced for user_id={user_id} "
            f"(pending within {PROFILE_BUILD_DEBOUNCE_TTL_SECONDS}s window)"
        )
        return False

    build_profile_task.apply_async(args=[user_id], countdown=countdown)
    logger.info(
        f"Scheduled debounced profile build for user_id={user_id} "
        f"(countdown={countdown}s)"
    )
    return True


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
