"""Durable chat sessions with Redis caching and an in-memory dev fallback."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import redis_client
from app.models.chat import ChatSessionRecord

from . import ChatContext, ChatIntent, ChatMessage, MessageRole

CHAT_SESSION_KEY_PREFIX = "chat:session"
_USE_CONFIGURED_REDIS = object()


def session_key(session_id: str) -> str:
    return f"{CHAT_SESSION_KEY_PREFIX}:{session_id}"


def serialize_context(context: ChatContext) -> str:
    return json.dumps(context.to_dict())


def _parse_message(raw: Dict[str, Any]) -> ChatMessage:
    intent_value = raw.get("intent")
    timestamp_value = raw.get("timestamp")
    return ChatMessage(
        role=MessageRole(raw["role"]),
        content=raw["content"],
        position_fen=raw.get("position_fen"),
        intent=ChatIntent(intent_value) if intent_value else None,
        timestamp=datetime.fromisoformat(timestamp_value) if timestamp_value else None,
        metadata=raw.get("metadata") or {},
    )


def deserialize_context(data: Any) -> ChatContext:
    payload = json.loads(data) if isinstance(data, (str, bytes, bytearray)) else data
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
    """Use Postgres as source of truth and Redis as an expiring read cache."""

    def __init__(
        self,
        redis: Any = _USE_CONFIGURED_REDIS,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        self._redis = redis_client if redis is _USE_CONFIGURED_REDIS else redis
        self._ttl = ttl_seconds if ttl_seconds is not None else settings.CHAT_SESSION_TTL_SECONDS
        self._memory: Dict[str, ChatContext] = {}

    @property
    def uses_redis(self) -> bool:
        return self._redis is not None

    def _cache(self, context: ChatContext) -> None:
        self._memory[context.session_id] = context
        if self._redis is None:
            return
        try:
            self._redis.setex(
                session_key(context.session_id), self._ttl, serialize_context(context)
            )
        except Exception as exc:
            logger.warning(f"Redis save failed for session {context.session_id}: {exc}")

    def get(self, session_id: str, db: Optional[Session] = None) -> Optional[ChatContext]:
        if not session_id:
            return None
        # Postgres is authoritative. Redis may contain a shorter context written
        # by an older deployment, so only use it as a legacy/cache fallback.
        if db is not None:
            record = db.query(ChatSessionRecord).filter_by(session_id=session_id).one_or_none()
            if record is not None:
                context = deserialize_context(record.context_json)
                self._cache(context)
                return context
        if self._redis is not None:
            try:
                raw = self._redis.get(session_key(session_id))
                if raw is not None:
                    return deserialize_context(raw)
            except Exception as exc:
                logger.warning(f"Redis get failed for session {session_id}: {exc}")
        context = self._memory.get(session_id)
        if context is not None:
            return context
        return None

    def save(self, context: ChatContext, db: Optional[Session] = None) -> None:
        if db is not None:
            if context.user_id is None:
                raise ValueError("Durable chat sessions require a user_id")
            try:
                record = db.query(ChatSessionRecord).filter_by(
                    session_id=context.session_id
                ).one_or_none()
                payload = context.to_dict()
                if record is None:
                    db.add(ChatSessionRecord(
                        session_id=context.session_id,
                        user_id=context.user_id,
                        context_json=payload,
                    ))
                else:
                    record.user_id = context.user_id
                    record.context_json = payload
                    record.updated_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
                raise
        self._cache(context)

    def delete(self, session_id: str, db: Optional[Session] = None) -> bool:
        if not session_id:
            return False
        existed = False
        if db is not None:
            record = db.query(ChatSessionRecord).filter_by(session_id=session_id).one_or_none()
            if record is not None:
                db.delete(record)
                db.commit()
                existed = True
        if self._redis is not None:
            try:
                existed = bool(self._redis.delete(session_key(session_id))) or existed
            except Exception as exc:
                logger.warning(f"Redis delete failed for session {session_id}: {exc}")
        if session_id in self._memory:
            del self._memory[session_id]
            existed = True
        return existed

    def list_for_user(
        self, user_id: int, limit: int = 20, db: Optional[Session] = None
    ) -> List[ChatContext]:
        sessions: Dict[str, ChatContext] = {}
        if db is not None:
            records = (
                db.query(ChatSessionRecord)
                .filter(ChatSessionRecord.user_id == user_id)
                .order_by(ChatSessionRecord.updated_at.desc())
                .limit(limit)
                .all()
            )
            for record in records:
                context = deserialize_context(record.context_json)
                sessions[context.session_id] = context
                self._cache(context)
        if self._redis is not None:
            try:
                for raw_key in self._redis.scan_iter(
                    match=f"{CHAT_SESSION_KEY_PREFIX}:*", count=100
                ):
                    key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
                    session_id = str(key).removeprefix(f"{CHAT_SESSION_KEY_PREFIX}:")
                    context = self.get(session_id, db=db)
                    if context is not None and context.user_id == user_id:
                        sessions.setdefault(context.session_id, context)
            except Exception as exc:
                logger.warning(f"Redis scan failed while listing chat sessions: {exc}")
        for context in self._memory.values():
            if context.user_id == user_id:
                sessions.setdefault(context.session_id, context)

        def updated_at(context: ChatContext) -> float:
            timestamps = [m.timestamp for m in context.conversation_history if m.timestamp]
            if not timestamps:
                return 0.0
            latest = max(timestamps)
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            return latest.timestamp()

        return sorted(sessions.values(), key=updated_at, reverse=True)[:limit]

    def active_session_count(self) -> int:
        if self._redis is None:
            return len(self._memory)
        try:
            return sum(1 for _ in self._redis.scan_iter(
                match=f"{CHAT_SESSION_KEY_PREFIX}:*", count=100
            ))
        except Exception as exc:
            logger.warning(f"Redis scan failed for session count: {exc}")
            return len(self._memory)
