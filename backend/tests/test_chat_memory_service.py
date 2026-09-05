"""Tests for chat-memory extraction (coaching semantic memories)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.models.chat import ChatSessionRecord
from app.models.semantic_memory import SemanticMemory
from app.models.user import User
from app.services.chat import ChatContext, ChatMessage, MessageRole
from app.services.chat.chess_coach import ChessCoach
from app.services.coaching.chat_memory_service import (
    build_exchange_memory_text,
    build_exchanges,
    content_id_for_exchange,
    sync_session_chat_memories,
)
from app.services.coaching.embedding_service import EMBEDDING_DIM
from app.tasks.chat_memory_tasks import (
    CHAT_MEMORY_DEBOUNCE_KEY_PREFIX,
    schedule_chat_memory_extraction,
)

SESSION_ID = "11111111-2222-3333-4444-555555555555"
ASKED_AT = datetime(2026, 2, 1, 10, 30, 0)


def _create_user(db) -> User:
    user = User(
        email="chat-memory@example.com",
        supabase_user_id="chat-memory-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _chat_message_dict(role: MessageRole, content: str) -> dict:
    return ChatMessage(role=role, content=content, timestamp=ASKED_AT).to_dict()


def _chat_message(role: MessageRole, content: str) -> ChatMessage:
    return ChatMessage(role=role, content=content, timestamp=ASKED_AT)


def _create_session_record(
    db,
    user: User,
    history: list[dict],
    session_id: str = SESSION_ID,
) -> ChatSessionRecord:
    payload = {
        "session_id": session_id,
        "user_id": user.id,
        "current_position": None,
        "conversation_history": history,
        "skill_level": "intermediate",
        "focus_areas": [],
        "recent_topics": [],
    }
    record = ChatSessionRecord(
        session_id=session_id,
        user_id=user.id,
        context_json=payload,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _exchange_history() -> list[dict]:
    return [
        _chat_message_dict(
            MessageRole.ASSISTANT,
            "Welcome. What would you like to work on today?",
        ),
        _chat_message_dict(
            MessageRole.USER,
            "I keep losing pieces in the middlegame.\nWhat should I focus on?",
        ),
        _chat_message_dict(
            MessageRole.ASSISTANT,
            "Track hanging pieces: before every move, scan for undefended "
            "pieces on both sides.  That single habit usually removes most "
            "one-move blunders at club level.",
        ),
    ]


def test_content_id_for_exchange_is_deterministic():
    assert content_id_for_exchange(SESSION_ID, 3) == content_id_for_exchange(
        SESSION_ID, 3
    )
    assert content_id_for_exchange(SESSION_ID, 3) != content_id_for_exchange(
        SESSION_ID, 4
    )


def test_build_exchange_memory_text_compresses_and_dates():
    text = build_exchange_memory_text(
        "I  keep   losing pieces.\n\nWhat now?",
        "Answer   with advice " * 100,
        ASKED_AT,
    )
    assert text.startswith("Coaching exchange (2026-02-01). Player asked:")
    assert "I keep losing pieces. What now?" in text
    assert "  " not in text
    assert "\n" not in text
    # The coach side is capped so one exchange stays one short memory.
    assert len(text) < 700


def test_build_exchanges_skips_unpaired_trailing_user_message():
    history = [
        _chat_message(MessageRole.USER, "question one"),
        _chat_message(MessageRole.ASSISTANT, "answer one"),
        _chat_message(MessageRole.USER, "question two"),
    ]

    exchanges = build_exchanges(history)

    assert len(exchanges) == 1
    assert exchanges[0]["exchange_index"] == 0
    assert exchanges[0]["user_content"] == "question one"
    assert exchanges[0]["assistant_content"] == "answer one"


@patch("app.services.coaching.chat_memory_service.embed_texts_sync")
def test_sync_embeds_coaching_memories(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    mock_embed.return_value = [[0.4] * EMBEDDING_DIM]

    user = _create_user(db)
    _create_session_record(db, user, _exchange_history())

    result = sync_session_chat_memories(db, SESSION_ID, user.id)

    assert result["status"] == "success"
    assert result["embedded_count"] == 1
    mock_embed.assert_called_once()
    (embedded_text,) = mock_embed.call_args.args[0]
    assert "Player asked: I keep losing pieces in the middlegame." in embedded_text

    memory = (
        db.query(SemanticMemory)
        .filter(
            SemanticMemory.user_id == user.id,
            SemanticMemory.content_type == "coaching",
        )
        .one()
    )
    assert memory.content_id == content_id_for_exchange(SESSION_ID, 1)
    assert "Player asked:" in memory.content_text
    assert memory.memory_metadata["session_id"] == SESSION_ID
    assert memory.memory_metadata["asked_at"] == ASKED_AT.isoformat()


@patch("app.services.coaching.chat_memory_service.embed_texts_sync")
def test_sync_is_idempotent_on_rerun(mock_embed, db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    mock_embed.return_value = [[0.4] * EMBEDDING_DIM]

    user = _create_user(db)
    _create_session_record(db, user, _exchange_history())

    first = sync_session_chat_memories(db, SESSION_ID, user.id)
    second = sync_session_chat_memories(db, SESSION_ID, user.id)

    assert first["embedded_count"] == 1
    assert second["status"] == "success"
    assert second["embedded_count"] == 0
    assert second["skipped_count"] == 1
    assert mock_embed.call_count == 1
    assert db.query(SemanticMemory).count() == 1


def test_sync_skips_when_embedding_unconfigured(db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    user = _create_user(db)
    _create_session_record(db, user, _exchange_history())

    result = sync_session_chat_memories(db, SESSION_ID, user.id)

    assert result["status"] == "skipped"
    assert result["reason"] == "embedding not configured"
    assert db.query(SemanticMemory).count() == 0


def test_sync_skips_unpaired_trailing_user_message(db, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    user = _create_user(db)
    _create_session_record(
        db,
        user,
        [
            _chat_message_dict(MessageRole.USER, "question with no reply yet"),
        ],
    )

    result = sync_session_chat_memories(db, SESSION_ID, user.id)

    assert result["status"] == "success"
    assert result["embedded_count"] == 0
    assert db.query(SemanticMemory).count() == 0


def test_sync_skips_missing_session(db):
    user = _create_user(db)

    result = sync_session_chat_memories(db, "no-such-session", user.id)

    assert result["status"] == "skipped"
    assert result["reason"] == "session not found"


@patch("app.tasks.chat_memory_tasks.redis_client", None)
@patch("app.tasks.chat_memory_tasks.extract_chat_memories_task.apply_async")
def test_schedule_chat_memory_without_redis(mock_apply_async):
    scheduled = schedule_chat_memory_extraction(7, "sess-1", countdown=30)

    assert scheduled is True
    mock_apply_async.assert_called_once_with(args=[7, "sess-1"], countdown=30)


@patch("app.tasks.chat_memory_tasks.redis_client")
@patch("app.tasks.chat_memory_tasks.extract_chat_memories_task.apply_async")
def test_schedule_chat_memory_debounce(mock_apply_async, mock_redis):
    mock_redis.set.return_value = False

    scheduled = schedule_chat_memory_extraction(9, "sess-2")

    assert scheduled is False
    mock_apply_async.assert_not_called()
    mock_redis.set.assert_called_once_with(
        f"{CHAT_MEMORY_DEBOUNCE_KEY_PREFIX}:sess-2",
        "1",
        nx=True,
        ex=300,
    )


class _CapturingAIClient:
    """Async stub that records the request and returns a fixed reply."""

    def __init__(self):
        self.captured = None

    async def chat_completion(self, messages, temperature, max_tokens):
        self.captured = messages
        return {"content": "ok"}


@pytest.mark.asyncio
async def test_llm_coach_reply_includes_recall_honesty_rule():
    ai_client = _CapturingAIClient()
    coach = ChessCoach(ai_client=ai_client)

    await coach._llm_coach_reply(
        "What was the first thing I said?",
        ChatContext(session_id="s1"),
        "Grounding facts block",
    )

    system_content = ai_client.captured[0]["content"]
    assert "Recall honesty" in system_content
    assert "do not have a record" in system_content


@pytest.mark.asyncio
@patch("app.tasks.chat_memory_tasks.redis_client", None)
@patch("app.tasks.chat_memory_tasks.extract_chat_memories_task.apply_async")
async def test_process_message_schedules_chat_memory_extraction(
    mock_apply_async, db, monkeypatch
):
    monkeypatch.delenv("TESTING", raising=False)
    user = _create_user(db)
    coach = ChessCoach()

    await coach.process_message(
        message="Let's work on my openings.",
        user_id=user.id,
        db=db,
    )

    mock_apply_async.assert_called_once()
    call_kwargs = mock_apply_async.call_args.kwargs
    assert call_kwargs.get("countdown") == 30
    (task_user_id, task_session_id) = call_kwargs["args"]
    assert task_user_id == user.id
    assert task_session_id
