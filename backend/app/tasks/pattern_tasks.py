"""
Celery tasks for debounced pattern detection after game analysis.

Debouncing strategy (P1-PR-05):
- ``analyze_game_task`` calls :func:`schedule_pattern_detection_for_user` on success.
- Redis SET NX ensures at most one pending pattern job per user within the debounce
  window, so batch analysis (N game tasks) queues one delayed run instead of N.
- Without Redis (local dev), each call enqueues directly with countdown.
- Manual refresh: ``POST /api/v1/users/{user_id}/patterns/analyze``.
"""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal, redis_client
from app.services.patterns import run_pattern_detection
from app.tasks.profile_tasks import schedule_profile_build_for_user
from app.tasks.embedding_tasks import schedule_pattern_embedding_for_user

PATTERN_DEBOUNCE_KEY_PREFIX = "pattern_detection_scheduled"
PATTERN_DEBOUNCE_TTL_SECONDS = 120
PATTERN_DEBOUNCE_COUNTDOWN_SECONDS = 60


def schedule_pattern_detection_for_user(
    user_id: int,
    *,
    countdown: int = PATTERN_DEBOUNCE_COUNTDOWN_SECONDS,
) -> bool:
    """
    Enqueue pattern detection for a user, debounced per user_id.

    Returns True when a new Celery task was scheduled, False when suppressed
    by an active debounce key (another run is already pending).
    """
    if redis_client is None:
        detect_patterns_task.apply_async(args=[user_id], countdown=countdown)
        logger.debug(
            f"Scheduled pattern detection for user_id={user_id} "
            f"(no Redis debounce, countdown={countdown}s)"
        )
        return True

    debounce_key = f"{PATTERN_DEBOUNCE_KEY_PREFIX}:{user_id}"
    if not redis_client.set(debounce_key, "1", nx=True, ex=PATTERN_DEBOUNCE_TTL_SECONDS):
        logger.debug(
            f"Pattern detection debounced for user_id={user_id} "
            f"(pending within {PATTERN_DEBOUNCE_TTL_SECONDS}s window)"
        )
        return False

    detect_patterns_task.apply_async(args=[user_id], countdown=countdown)
    logger.info(
        f"Scheduled debounced pattern detection for user_id={user_id} "
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
    name="app.tasks.pattern_tasks.detect_patterns_task",
)
def detect_patterns_task(self, user_id: int):
    """
    Celery task: run deterministic pattern detection and persist snapshots.

    Idempotent — safe to retry; unique DB constraints prevent duplicate rows.
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting pattern detection for user_id={user_id}")
        result = run_pattern_detection(db, user_id, persist=True)
        logger.info(
            f"Pattern detection complete user_id={user_id}: "
            f"{result.pattern_count} patterns from {result.games_considered} games"
        )
        schedule_profile_build_for_user(user_id)
        schedule_pattern_embedding_for_user(user_id)
        return {
            "status": "success",
            "user_id": user_id,
            "pattern_count": result.pattern_count,
            "games_considered": result.games_considered,
        }
    except Exception as exc:
        db.rollback()
        logger.error(f"Pattern detection failed for user_id={user_id}: {exc}")
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
