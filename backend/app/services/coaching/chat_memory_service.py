"""Chat-memory extractor — compress coaching exchanges into semantic_memory.

Memory doctrine (docs §7.2/§7.3): never embed raw conversation dumps. Each
user→assistant exchange is compressed into a single short coaching-memory
sentence and upserted into the ``coaching`` slice of ``semantic_memory`` keyed
by a deterministic content id, so extraction re-runs are idempotent and a
growing session never duplicates rows.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
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

# Must match the LLM window in chess_coach._llm_coach_reply
# (get_recent_messages(7)[:-1]) — messages older than this are summarized.
THREAD_WINDOW_MESSAGES = 7

_SUMMARY_SYSTEM_PROMPT = (
    "You maintain a rolling summary of the earlier part of a chess-coaching "
    "thread (the part that has scrolled out of the model's recent window). "
    "Update the provided previous summary so it covers both the previous "
    "summary and the new transcript excerpt: keep the questions the player "
    "asked, the key coaching advice given, openings / weaknesses / goals "
    "discussed, and any decisions made. Be factual and compact — under 250 "
    "words. Output only the summary text."
)

_TRANSCRIPT_MESSAGE_CHARS = 300
_TRANSCRIPT_TOTAL_CHARS = 24000

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


def content_id_for_interview_summary(session_id: str) -> int:
    """Deterministic 48-bit id for a session's interview summary row."""
    digest = md5(f"{session_id}:interview-summary".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def build_interview_memory_text(summary: str) -> str:
    """Compress the interview goal summary into one dated memory sentence."""
    date_prefix = f"Interview summary ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
    body = _collapse_whitespace(summary)[:400]
    return f"{date_prefix}. {body}"


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
    for exchange in exchanges:
        exchange["content_id"] = content_id_for_exchange(
            session_id, exchange["exchange_index"]
        )

    interview_id = content_id_for_interview_summary(session_id)
    interview_text: Optional[str] = None
    if context.interview_summary:
        interview_text = build_interview_memory_text(context.interview_summary)

    if not exchanges and interview_text is None:
        return {
            "status": "success",
            "embedded_count": 0,
            "skipped_count": 0,
        }

    if not is_embedding_configured():
        return {
            "status": "skipped",
            "embedded_count": 0,
            "skipped_count": len(exchanges) + (1 if interview_text else 0),
            "reason": "embedding not configured",
        }

    candidate_ids = [exchange["content_id"] for exchange in exchanges]
    if interview_text is not None:
        candidate_ids.append(interview_id)

    existing_ids: set[int] = set()
    interview_row: Optional[SemanticMemory] = None
    for memory in (
        db.query(SemanticMemory)
        .filter(
            SemanticMemory.user_id == user_id,
            SemanticMemory.content_type == CONTENT_TYPE_COACHING,
            SemanticMemory.content_id.in_(candidate_ids),
        )
        .all()
    ):
        if memory.content_id is None:
            continue
        existing_ids.add(int(memory.content_id))
        if int(memory.content_id) == interview_id:
            interview_row = memory

    pending = [
        exchange for exchange in exchanges if exchange["content_id"] not in existing_ids
    ]

    # Persist the interview summary when new, and refresh it when the coach
    # refined the summary in a later exchange.
    include_interview = interview_text is not None and (
        interview_row is None or interview_row.content_text != interview_text
    )

    if not pending and not include_interview:
        return {
            "status": "success",
            "embedded_count": 0,
            "skipped_count": len(exchanges),
        }

    targets: list[tuple[int, str, dict[str, Any]]] = []
    for exchange in pending:
        metadata: dict[str, Any] = {"session_id": session_id}
        if exchange["asked_at"] is not None:
            metadata["asked_at"] = exchange["asked_at"].isoformat()
        targets.append(
            (
                exchange["content_id"],
                build_exchange_memory_text(
                    exchange["user_content"],
                    exchange["assistant_content"],
                    exchange["asked_at"],
                ),
                metadata,
            )
        )
    if include_interview:
        targets.append(
            (
                interview_id,
                interview_text,
                {"session_id": session_id, "kind": "interview_summary"},
            )
        )

    try:
        embeddings = embed_texts_sync([target[1] for target in targets])
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

    for (content_id, text, metadata), vector in zip(targets, embeddings):
        upsert_semantic_memory(
            db,
            user_id=user_id,
            content_type=CONTENT_TYPE_COACHING,
            content_id=content_id,
            content_text=text,
            embedding=vector,
            metadata=metadata,
        )

    embedded_count = len(targets)
    skipped_count = len(exchanges) - len(pending)
    logger.info(
        f"Chat memories synced session={session_id} user_id={user_id}: "
        f"embedded={embedded_count} skipped={skipped_count}"
    )
    return {
        "status": "success",
        "embedded_count": embedded_count,
        "skipped_count": skipped_count,
    }


def sync_session_thread_summary(
    db: Session,
    session_id: str,
    user_id: int,
) -> dict[str, Any]:
    """
    Maintain a rolling summary of everything older than the LLM window.

    User directive: summarize the context instead of silently cutting it. The
    messages that have scrolled out of ``THREAD_WINDOW_MESSAGES`` are appended
    to the stored rolling summary (one LLM call per debounce run, only when
    new out-of-window messages exist), and the result is stored on the session
    record as ``early_summary`` / ``summary_upto`` so the coach can inject it.
    """
    from app.models.chat import ChatSessionRecord

    record = (
        db.query(ChatSessionRecord)
        .filter_by(session_id=session_id, user_id=user_id)
        .one_or_none()
    )
    if record is None:
        return {"status": "skipped", "reason": "session not found"}

    payload = record.context_json if isinstance(record.context_json, dict) else {}
    history = payload.get("conversation_history") or []
    summary_upto = int(payload.get("summary_upto") or 0)
    window_start = max(0, len(history) - THREAD_WINDOW_MESSAGES)
    if window_start <= summary_upto:
        return {
            "status": "success",
            "updated": False,
            "reason": "no messages outside the window",
        }

    pending = history[summary_upto:window_start]
    transcript_lines = []
    for message in pending:
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        role = str(message.get("role") or "unknown")
        transcript_lines.append(f"{role}: {' '.join(content.split())[:_TRANSCRIPT_MESSAGE_CHARS]}")
    if not transcript_lines:
        return {"status": "success", "updated": False, "reason": "empty transcript"}
    transcript = "\n".join(transcript_lines)[-_TRANSCRIPT_TOTAL_CHARS:]
    previous_summary = str(payload.get("early_summary") or "")

    try:
        from app.services.integration.ai_client import get_ai_client

        result = asyncio.run(
            get_ai_client().chat_completion(
                messages=[
                    {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Previous summary (may be empty):\n{previous_summary}\n\n"
                            f"New transcript excerpt to fold in:\n{transcript}"
                        ),
                    },
                ],
                temperature=0.2,
                max_tokens=800,
            )
        )
    except Exception as exc:
        logger.error(
            f"Thread summary generation failed session={session_id}: {exc}"
        )
        return {"status": "failed", "reason": str(exc)}

    summary_text = str(result.get("content") or "").strip()
    if not summary_text:
        return {"status": "failed", "reason": "empty summary response"}

    # Re-read and touch only the summary keys to minimize a lost-update race
    # with the API process appending new messages.
    record = (
        db.query(ChatSessionRecord)
        .filter_by(session_id=session_id, user_id=user_id)
        .one_or_none()
    )
    if record is None:
        return {"status": "skipped", "reason": "session deleted during summary"}
    fresh_payload = (
        dict(record.context_json) if isinstance(record.context_json, dict) else {}
    )
    fresh_payload["early_summary"] = summary_text
    fresh_payload["summary_upto"] = window_start
    record.context_json = fresh_payload
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        f"Thread summary updated session={session_id}: "
        f"covers {window_start}/{len(history)} messages"
    )
    return {"status": "success", "updated": True, "summary_upto": window_start}
