"""
Redis-backed chat session store (P1-CM-01).

Persists :class:`ChatContext` as JSON under ``chat:session:{session_id}`` with TTL.
When ``redis_client`` is unavailable (local dev without Redis), falls back to an
in-process dict — same pattern as ``pattern_tasks.schedule_pattern_detection_for_user``.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.core.database import redis_client

from . import ChatContext, ChatIntent, ChatMessage, MessageRole

CHAT_SESSION_KEY_PREFIX = "chat:session"


def session_key(session_id: str) -> str:
    """Build the Redis key for a chat session."""
    return f"{CHAT_SESSION_KEY_PREFIX}:{session_id}"


def serialize_context(context: ChatContext) -> str:
    """Serialize a chat context to JSON."""
    return json.dumps(context.to_dict())


def _parse_message(raw: Dict[str, Any]) -> ChatMessage:
    intent_value = raw.get("intent")
    intent = ChatIntent(intent_value) if intent_value else None

    timestamp_value = raw.get("timestamp")
    timestamp = None
    if timestamp_value:
        timestamp = datetime.fromisoformat(timestamp_value)

    return ChatMessage(
        role=MessageRole(raw["role"]),
        content=raw["content"],
        position_fen=raw.get("position_fen"),
        intent=intent,
        timestamp=timestamp,
        metadata=raw.get("metadata") or {},
    )


def deserialize_context(data: str) -> ChatContext:
    """Deserialize JSON into a :class:`ChatContext`."""
    payload = json.loads(data)
    history = [_parse_message(msg) for msg in payload.get("conversation_history", [])]
    return ChatContext(
        session_id=payload["session_id"],
        user_id=payload.get("user_id"),
        current_position=payload.get("current_position"),
        conversation_history=history,
        skill_level=payload.get("skill_level", "intermediate"),
        focus_areas=payload.get("focus_areas") or [],
        recent_topics=payload.get("recent_topics") or [],
    )


class ChatSessionStore:
    """Load/save chat sessions via Redis with in-memory fallback."""

    def __init__(
        self,
        redis: Optional[Any] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        self._redis = redis if redis is not None else redis_client
        self._ttl = ttl_seconds if ttl_seconds is not None else settings.CHAT_SESSION_TTL_SECONDS
        self._memory: Dict[str, ChatContext] = {}

    @property
    def uses_redis(self) -> bool:
        return self._redis is not None

    def get(self, session_id: str) -> Optional[ChatContext]:
        """Return a session by ID, or ``None`` if missing/expired."""
        if not session_id:
            return None

        if self._redis is None:
            return self._memory.get(session_id)

        try:
            raw = self._redis.get(session_key(session_id))
            if raw is not None:
                return deserialize_context(raw)
        except Exception as exc:
            logger.warning(f"Redis get failed for session {session_id}: {exc}")

        return self._memory.get(session_id)

    def save(self, context: ChatContext) -> None:
        """Persist a session, refreshing TTL on Redis."""
        if self._redis is None:
            self._memory[context.session_id] = context
            return

        try:
            payload = serialize_context(context)
            self._redis.setex(session_key(context.session_id), self._ttl, payload)
        except Exception as exc:
            logger.warning(
                f"Redis save failed for session {context.session_id}: {exc}; "
                "using in-memory fallback"
            )
            self._memory[context.session_id] = context

    def delete(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        if not session_id:
            return False

        existed = False

        if self._redis is not None:
            try:
                deleted = self._redis.delete(session_key(session_id))
                existed = bool(deleted)
            except Exception as exc:
                logger.warning(f"Redis delete failed for session {session_id}: {exc}")

        if session_id in self._memory:
            del self._memory[session_id]
            existed = True

        return existed

    def list_for_user(self, user_id: int, limit: int = 20) -> List[ChatContext]:
        """Return a user's active sessions, newest activity first."""
        sessions: Dict[str, ChatContext] = {}

        if self._redis is not None:
            try:
                for raw_key in self._redis.scan_iter(
                    match=f"{CHAT_SESSION_KEY_PREFIX}:*", count=100
                ):
                    key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
                    session_id = str(key).removeprefix(f"{CHAT_SESSION_KEY_PREFIX}:")
                    context = self.get(session_id)
                    if context is not None and context.user_id == user_id:
                        sessions[context.session_id] = context
            except Exception as exc:
                logger.warning(f"Redis scan failed while listing chat sessions: {exc}")

        for context in self._memory.values():
            if context.user_id == user_id:
                sessions[context.session_id] = context

        def updated_at(context: ChatContext) -> datetime:
            timestamps = [message.timestamp for message in context.conversation_history if message.timestamp]
            return max(timestamps) if timestamps else datetime.min

        return sorted(sessions.values(), key=updated_at, reverse=True)[:limit]

    def active_session_count(self) -> int:
        """Count active sessions (Redis scan or in-memory dict size)."""
        if self._redis is None:
            return len(self._memory)

        try:
            count = 0
            pattern = f"{CHAT_SESSION_KEY_PREFIX}:*"
            for _ in self._redis.scan_iter(match=pattern, count=100):
                count += 1
            return count
        except Exception as exc:
            logger.warning(f"Redis scan failed for session count: {exc}")
            return len(self._memory)
