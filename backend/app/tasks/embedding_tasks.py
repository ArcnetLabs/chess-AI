"""
Celery tasks for debounced pattern embedding after pattern detection (P3-CM-02).

Debouncing strategy:
- ``detect_patterns_task`` calls :func:`schedule_pattern_embedding_for_user` on success.
- Redis SET NX ensures at most one pending embedding job per user within the debounce
  window, so rapid pattern reruns queue one delayed run instead of many.
- Without Redis (local dev), each call enqueues directly with countdown.
"""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal, redis_client
from app.services.coaching.embedding_pipeline import sync_user_pattern_embeddings

EMBEDDING_DEBOUNCE_KEY_PREFIX = "pattern_embedding_scheduled"
EMBEDDING_DEBOUNCE_TTL_SECONDS = 120
EMBEDDING_DEBOUNCE_COUNTDOWN_SECONDS = 30


def schedule_pattern_embedding_for_user(
    user_id: int,
    *,
    countdown: int = EMBEDDING_DEBOUNCE_COUNTDOWN_SECONDS,
) -> bool:
    """
    Enqueue pattern embedding for a user, debounced per user_id.

    Returns True when a new Celery task was scheduled, False when suppressed
    by an active debounce key (another run is already pending).
    """
    if redis_client is None:
        embed_user_patterns_task.apply_async(args=[user_id], countdown=countdown)
        logger.debug(
            f"Scheduled pattern embedding for user_id={user_id} "
            f"(no Redis debounce, countdown={countdown}s)"
        )
        return True

    debounce_key = f"{EMBEDDING_DEBOUNCE_KEY_PREFIX}:{user_id}"
    if not redis_client.set(debounce_key, "1", nx=True, ex=EMBEDDING_DEBOUNCE_TTL_SECONDS):
        logger.debug(
            f"Pattern embedding debounced for user_id={user_id} "
            f"(pending within {EMBEDDING_DEBOUNCE_TTL_SECONDS}s window)"
        )
        return False

    embed_user_patterns_task.apply_async(args=[user_id], countdown=countdown)
    logger.info(
        f"Scheduled debounced pattern embedding for user_id={user_id} "
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
    name="app.tasks.embedding_tasks.embed_user_patterns_task",
)
def embed_user_patterns_task(self, user_id: int):
    """
    Celery task: embed player patterns into semantic_memory.

    Idempotent — safe to retry; upsert by content_type + content_id.
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting pattern embedding for user_id={user_id}")
        result = sync_user_pattern_embeddings(db, user_id)
        logger.info(
            f"Pattern embedding complete user_id={user_id}: "
            f"status={result['status']} embedded={result.get('embedded_count', 0)}"
        )
        return {"user_id": user_id, **result}
    except Exception as exc:
        db.rollback()
        logger.error(f"Pattern embedding failed for user_id={user_id}: {exc}")
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
