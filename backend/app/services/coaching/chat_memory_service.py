"""Chat-memory extractor — compress coaching exchanges into semantic_memory.

Memory doctrine (docs §7.2/§7.3): never embed raw conversation dumps. Each
user→assistant exchange is compressed into a single short coaching-memory
sentence and upserted into the ``coaching`` slice of ``semantic_memory`` keyed
by a deterministic content id, so extraction re-runs are idempotent and a
growing session never duplicates rows.
"""
from __future__ import annotations

import re
from datetime import datetime
from hashlib import md5
from typing import Any, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.semantic_memory import SemanticMemory
from app.services.coaching.embedding_pipeline import upsert_semantic_memory
from app.services.coaching.embedding_service import (
    embed_texts_sync,
    is_embedding_configured,
)

CONTENT_TYPE_COACHING = "coaching"

# Cap the extraction sweep so one oversized session cannot dominate the
# embedding budget; the most recent exchanges are the useful ones. Exchange
# indexes are assigned over the FULL history before this slice, so content
# ids stay stable as the session grows.
MAX_EXCHANGES_PER_RUN = 20

_QUESTION_MAX_CHARS = 220
_ANSWER_MAX_CHARS = 320

_WS_RUN = re.compile(r"\s+")


def content_id_for_exchange(session_id: str, exchange_index: int) -> int:
    """Deterministic 48-bit id for a session exchange (stable across re-runs)."""
    digest = md5(f"{session_id}:{exchange_index}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _collapse_whitespace(text: str) -> str:
    return _WS_RUN.sub(" ", text or "").strip()


def build_exchange_memory_text(
    user_content: str,
    assistant_content: str,
    timestamp: Optional[datetime],
) -> str:
    """Compress one coaching exchange into a single memory sentence."""
    date_prefix = "Coaching exchange"
    if timestamp is not None:
        date_prefix = f"{date_prefix} ({timestamp.strftime('%Y-%m-%d')})"
    question = _collapse_whitespace(user_content)[:_QUESTION_MAX_CHARS]
    answer = _collapse_whitespace(assistant_content)[:_ANSWER_MAX_CHARS]
    return f"{date_prefix}. Player asked: {question} | Coach: {answer}"


def _message_role(message: Any) -> str:
    role = getattr(message, "role", None)
    return getattr(role, "value", None) or str(role or "")


def build_exchanges(history: list) -> list[dict[str, Any]]:
    """Pair user messages with the assistant reply that follows them.

    Exchange indexes are 0-based positions of the user message in the full
    history, so ids stay stable as the conversation grows. An unpaired
    trailing user message (assistant reply not yet written) is skipped, and
    only the most recent :data:`MAX_EXCHANGES_PER_RUN` exchanges are returned.
    """
    exchanges: list[dict[str, Any]] = []
    pending_user: Optional[tuple[int, Any]] = None
    for index, message in enumerate(history):
        role = _message_role(message)
        if role == "user":
            pending_user = (index, message)
        elif role == "assistant" and pending_user is not None:
            user_index, user_message = pending_user
            pending_user = None
            exchanges.append(
                {
                    "exchange_index": user_index,
                    "user_content": user_message.content,
                    "assistant_content": message.content,
                    "asked_at": user_message.timestamp,
                }
            )
    return exchanges[-MAX_EXCHANGES_PER_RUN:]


def sync_session_chat_memories(
    db: Session,
    session_id: str,
    user_id: int,
) -> dict[str, Any]:
    """
    Extract + embed coaching memories for one chat session (idempotent).

    Loads the durable session record, pairs user→assistant exchanges, skips
    exchanges already embedded for this user, embeds the rest in one batch,
    and upserts them as ``coaching`` semantic memories.

    Returns stats: ``{status, embedded_count, skipped_count, reason?}``.
    """
    from app.models.chat import ChatSessionRecord
    from app.services.chat.session_store import deserialize_context

    record = (
        db.query(ChatSessionRecord)
        .filter_by(session_id=session_id, user_id=user_id)
        .one_or_none()
    )
    if record is None:
        return {
            "status": "skipped",
            "embedded_count": 0,
            "skipped_count": 0,
            "reason": "session not found",
        }

    context = deserialize_context(record.context_json)
    exchanges = build_exchanges(context.conversation_history)
    if not exchanges:
        return {
            "status": "success",
            "embedded_count": 0,
            "skipped_count": 0,
        }

    for exchange in exchanges:
        exchange["content_id"] = content_id_for_exchange(
            session_id, exchange["exchange_index"]
        )

    if not is_embedding_configured():
        return {
            "status": "skipped",
            "embedded_count": 0,
            "skipped_count": len(exchanges),
            "reason": "embedding not configured",
        }

    existing_ids: set[int] = set()
    candidate_ids = [exchange["content_id"] for exchange in exchanges]
    for memory in (
        db.query(SemanticMemory)
        .filter(
            SemanticMemory.user_id == user_id,
            SemanticMemory.content_type == CONTENT_TYPE_COACHING,
            SemanticMemory.content_id.in_(candidate_ids),
        )
        .all()
    ):
        if memory.content_id is not None:
            existing_ids.add(int(memory.content_id))

    pending = [
        exchange for exchange in exchanges if exchange["content_id"] not in existing_ids
    ]
    if not pending:
        return {
            "status": "success",
            "embedded_count": 0,
            "skipped_count": len(exchanges),
        }

    texts = [
        build_exchange_memory_text(
            exchange["user_content"],
            exchange["assistant_content"],
            exchange["asked_at"],
        )
        for exchange in pending
    ]
    try:
        embeddings = embed_texts_sync(texts)
    except Exception as exc:
        logger.error(
            f"Chat memory embedding failed session={session_id} user_id={user_id}: {exc}"
        )
        return {
            "status": "failed",
            "embedded_count": 0,
            "skipped_count": len(exchanges) - len(pending),
            "reason": str(exc),
        }

    for exchange, text, vector in zip(pending, texts, embeddings):
        metadata: dict[str, Any] = {"session_id": session_id}
        if exchange["asked_at"] is not None:
            metadata["asked_at"] = exchange["asked_at"].isoformat()
        upsert_semantic_memory(
            db,
            user_id=user_id,
            content_type=CONTENT_TYPE_COACHING,
            content_id=exchange["content_id"],
            content_text=text,
            embedding=vector,
            metadata=metadata,
        )

    embedded_count = len(pending)
    skipped_count = len(exchanges) - embedded_count
    logger.info(
        f"Chat memories synced session={session_id} user_id={user_id}: "
        f"embedded={embedded_count} skipped={skipped_count}"
    )
    return {
        "status": "success",
        "embedded_count": embedded_count,
        "skipped_count": skipped_count,
    }
