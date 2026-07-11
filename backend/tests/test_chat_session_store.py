"""Tests for Redis-backed chat session store (P1-CM-01)."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.services.chat import ChatContext, ChatIntent, ChatMessage, MessageRole
from app.services.chat.session_store import (
    CHAT_SESSION_KEY_PREFIX,
    ChatSessionStore,
    deserialize_context,
    serialize_context,
    session_key,
)


def _sample_context(session_id: str = "sess-1", user_id: int = 42) -> ChatContext:
    context = ChatContext(
        session_id=session_id,
        user_id=user_id,
        current_position="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        skill_level="intermediate",
        focus_areas=["tactics"],
        recent_topics=["openings"],
    )
    context.add_message(
        ChatMessage(
            role=MessageRole.USER,
            content="Hello coach",
            intent=ChatIntent.SMALL_TALK,
            timestamp=datetime(2026, 5, 26, 12, 0, 0),
            metadata={"source": "test"},
        )
    )
    return context


class TestSerialization:
    def test_round_trip_preserves_context(self):
        original = _sample_context()
        restored = deserialize_context(serialize_context(original))

        assert restored.session_id == original.session_id
        assert restored.user_id == original.user_id
        assert restored.current_position == original.current_position
        assert restored.skill_level == original.skill_level
        assert restored.focus_areas == original.focus_areas
        assert restored.recent_topics == original.recent_topics
        assert len(restored.conversation_history) == 1
        assert restored.conversation_history[0].role == MessageRole.USER
        assert restored.conversation_history[0].intent == ChatIntent.SMALL_TALK
        assert restored.conversation_history[0].metadata == {"source": "test"}

    def test_session_key_format(self):
        assert session_key("abc-123") == f"{CHAT_SESSION_KEY_PREFIX}:abc-123"


class TestChatSessionStoreMemoryFallback:
    def test_save_and_get_without_redis(self):
        store = ChatSessionStore(redis=None, ttl_seconds=3600)
        context = _sample_context("mem-1")

        store.save(context)
        loaded = store.get("mem-1")

        assert loaded is not None
        assert loaded.session_id == "mem-1"
        assert loaded.user_id == 42
        assert len(loaded.conversation_history) == 1

    def test_get_missing_returns_none(self):
        store = ChatSessionStore(redis=None)
        assert store.get("missing") is None

    def test_delete_removes_session(self):
        store = ChatSessionStore(redis=None)
        store.save(_sample_context("del-1"))

        assert store.delete("del-1") is True
        assert store.get("del-1") is None
        assert store.delete("del-1") is False

    def test_active_session_count_in_memory(self):
        store = ChatSessionStore(redis=None)
        store.save(_sample_context("c1"))
        store.save(_sample_context("c2"))

        assert store.active_session_count() == 2

    def test_list_for_user_returns_only_owned_sessions_newest_first(self):
        store = ChatSessionStore(redis=None)
        older = _sample_context("older", user_id=42)
        newer = _sample_context("newer", user_id=42)
        newer.conversation_history[0].timestamp = datetime(2026, 5, 27, 12, 0, 0)
        other = _sample_context("other", user_id=7)
        store.save(older)
        store.save(newer)
        store.save(other)

        sessions = store.list_for_user(42)

        assert [session.session_id for session in sessions] == ["newer", "older"]


class TestChatSessionStoreRedis:
    def test_save_uses_setex_with_ttl(self):
        mock_redis = MagicMock()
        store = ChatSessionStore(redis=mock_redis, ttl_seconds=86400)
        context = _sample_context("redis-1")

        store.save(context)

        mock_redis.setex.assert_called_once()
        key, ttl, payload = mock_redis.setex.call_args[0]
        assert key == session_key("redis-1")
        assert ttl == 86400
        assert json.loads(payload)["session_id"] == "redis-1"

    def test_get_deserializes_from_redis(self):
        mock_redis = MagicMock()
        context = _sample_context("redis-2")
        mock_redis.get.return_value = serialize_context(context)
        store = ChatSessionStore(redis=mock_redis)

        loaded = store.get("redis-2")

        mock_redis.get.assert_called_once_with(session_key("redis-2"))
        assert loaded is not None
        assert loaded.session_id == "redis-2"

    def test_get_returns_none_when_key_missing(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        store = ChatSessionStore(redis=mock_redis)

        assert store.get("absent") is None

    def test_delete_calls_redis_delete(self):
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 1
        store = ChatSessionStore(redis=mock_redis)

        assert store.delete("redis-3") is True
        mock_redis.delete.assert_called_once_with(session_key("redis-3"))

    def test_redis_get_failure_falls_back_to_memory(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = ConnectionError("redis down")
        store = ChatSessionStore(redis=mock_redis)
        store._memory["fallback-1"] = _sample_context("fallback-1")

        loaded = store.get("fallback-1")

        assert loaded is not None
        assert loaded.session_id == "fallback-1"

    def test_redis_save_failure_falls_back_to_memory(self):
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = ConnectionError("redis down")
        store = ChatSessionStore(redis=mock_redis)
        context = _sample_context("fallback-2")

        store.save(context)

        assert store.get("fallback-2") is not None

    def test_active_session_count_scans_redis_keys(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = iter(
            [session_key("a"), session_key("b")]
        )
        store = ChatSessionStore(redis=mock_redis)

        assert store.active_session_count() == 2
        mock_redis.scan_iter.assert_called_once_with(
            match=f"{CHAT_SESSION_KEY_PREFIX}:*",
            count=100,
        )


class TestChessCoachSessionIntegration:
    @pytest.mark.asyncio
    async def test_process_message_persists_session_in_memory_store(self):
        from app.services.chat.chess_coach import ChessCoach

        store = ChatSessionStore(redis=None)
        coach = ChessCoach(session_store=store)

        response = await coach.process_message(message="Hi there!")

        assert response.session_id is not None
        session = coach.get_session(response.session_id)
        assert session is not None
        assert len(session.conversation_history) == 2

    @pytest.mark.asyncio
    async def test_process_message_resumes_existing_session(self):
        from app.services.chat.chess_coach import ChessCoach

        store = ChatSessionStore(redis=None)
        coach = ChessCoach(session_store=store)

        first = await coach.process_message(message="Hello")
        second = await coach.process_message(
            message="Thanks",
            session_id=first.session_id,
        )

        assert second.session_id == first.session_id
        session = coach.get_session(first.session_id)
        assert len(session.conversation_history) == 4

    def test_create_and_delete_session(self):
        from app.services.chat.chess_coach import ChessCoach

        store = ChatSessionStore(redis=None)
        coach = ChessCoach(session_store=store)

        session = coach.create_session(user_id=99)
        assert coach.get_session(session.session_id) is not None
        assert len(session.conversation_history) == 1
        assert session.conversation_history[0].role == MessageRole.ASSISTANT
        assert coach.delete_session(session.session_id) is True
        assert coach.get_session(session.session_id) is None
