"""
Celery tasks for chat-memory extraction after each coaching exchange.

Scheduling strategy mirrors ``embedding_tasks``: a Redis SET NX debounce key
per session ensures a burst of messages queues one delayed extraction run
instead of many. Without Redis (local dev), each call enqueues directly with
a countdown. The task itself is idempotent — re-runs only embed exchanges
that have no ``coaching`` semantic-memory row yet.
"""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal, redis_client

CHAT_MEMORY_DEBOUNCE_KEY_PREFIX = "chat_memory_scheduled"
CHAT_MEMORY_DEBOUNCE_TTL_SECONDS = 300
CHAT_MEMORY_DEBOUNCE_COUNTDOWN_SECONDS = 30


def schedule_chat_memory_extraction(
    user_id: int,
    session_id: str,
    *,
    countdown: int = CHAT_MEMORY_DEBOUNCE_COUNTDOWN_SECONDS,
) -> bool:
    """
    Enqueue chat-memory extraction for a session, debounced per session_id.

    Returns True when a new Celery task was scheduled, False when suppressed
    by an active debounce key (another run is already pending).
    """
    if redis_client is None:
        extract_chat_memories_task.apply_async(
            args=[user_id, session_id], countdown=countdown
        )
        logger.debug(
            f"Scheduled chat memory extraction session={session_id} "
            f"(no Redis debounce, countdown={countdown}s)"
        )
        return True

    debounce_key = f"{CHAT_MEMORY_DEBOUNCE_KEY_PREFIX}:{session_id}"
    if not redis_client.set(
        debounce_key, "1", nx=True, ex=CHAT_MEMORY_DEBOUNCE_TTL_SECONDS
    ):
        logger.debug(
            f"Chat memory extraction debounced session={session_id} "
            f"(pending within {CHAT_MEMORY_DEBOUNCE_TTL_SECONDS}s window)"
        )
        return False

    extract_chat_memories_task.apply_async(args=[user_id, session_id], countdown=countdown)
    logger.info(
        f"Scheduled debounced chat memory extraction session={session_id} "
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
    name="app.tasks.chat_memory_tasks.extract_chat_memories_task",
)
def extract_chat_memories_task(self, user_id: int, session_id: str):
    """
    Celery task: compress this session's exchanges into semantic_memory.

    Idempotent — safe to retry; upsert by content_type + deterministic
    per-exchange content_id.
    """
    db = SessionLocal()
    try:
        from app.services.coaching.chat_memory_service import sync_session_chat_memories

        logger.info(f"Starting chat memory extraction session={session_id}")
        result = sync_session_chat_memories(db, session_id, user_id)
        logger.info(
            f"Chat memory extraction complete session={session_id}: "
            f"status={result['status']} embedded={result.get('embedded_count', 0)}"
        )
        return {"session_id": session_id, "user_id": user_id, **result}
    except Exception as exc:
        db.rollback()
        logger.error(f"Chat memory extraction failed session={session_id}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "status": "failed",
            "session_id": session_id,
            "user_id": user_id,
            "error": str(exc),
            "retries": self.request.retries,
        }
    finally:
        db.close()
