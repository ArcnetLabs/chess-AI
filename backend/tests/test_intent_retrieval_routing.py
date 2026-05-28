"""Tests for intent → retrieval content_type routing (P3-CC-01)."""

from unittest.mock import patch

import pytest

from app.models.user import User
from app.services.chat import ChatIntent
from app.services.chat.chess_coach import ChessCoach
from app.services.chat.context_assembler import (
    assemble_coach_context,
    assemble_coach_context_async,
)
from app.services.chat.intent_classifier import (
    CONTENT_TYPE_COACHING,
    CONTENT_TYPE_PATTERN,
    IntentClassifier,
)


@pytest.fixture
def classifier():
    return IntentClassifier()


@pytest.fixture
def routing_user(db):
    user = User(
        email="intent-routing@example.com",
        supabase_user_id="intent-routing-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.mark.parametrize("intent", [ChatIntent.SMALL_TALK, ChatIntent.UNKNOWN])
def test_retrieval_content_types_skips_semantic_retrieval(classifier, intent):
    assert classifier.retrieval_content_types(intent, "hello there") == []


@pytest.mark.parametrize(
    "intent",
    [
        ChatIntent.GENERAL_QUESTION,
        ChatIntent.ANALYZE_POSITION,
        ChatIntent.EXPLAIN_MOVE,
        ChatIntent.COMPARE_MOVES,
    ],
)
def test_retrieval_content_types_default_pattern(classifier, intent):
    assert classifier.retrieval_content_types(intent, "How do I improve?") == [
        CONTENT_TYPE_PATTERN
    ]


@pytest.mark.parametrize(
    "message",
    [
        "Do you remember what we discussed about endgames?",
        "What did my coach say last time?",
        "What was your previous advice on tactics?",
        "Can you coach me on openings?",
    ],
)
def test_retrieval_content_types_includes_coaching_keywords(classifier, message):
    result = classifier.retrieval_content_types(ChatIntent.GENERAL_QUESTION, message)
    assert result == [CONTENT_TYPE_PATTERN, CONTENT_TYPE_COACHING]


def test_retrieval_content_types_pattern_only_without_keywords(classifier):
    result = classifier.retrieval_content_types(
        ChatIntent.GENERAL_QUESTION, "How can I improve my endgames?"
    )
    assert result == [CONTENT_TYPE_PATTERN]


@patch("app.services.chat.context_assembler.retrieve_semantic_memories")
def test_assemble_coach_context_skips_retrieval_when_content_types_empty(
    mock_retrieve, db, routing_user
):
    context = assemble_coach_context(
        db,
        routing_user.id,
        query_text="hello",
        content_types=[],
    )

    mock_retrieve.assert_not_called()
    assert "Player Context" in context


@pytest.mark.asyncio
@patch("app.services.chat.context_assembler.retrieve_semantic_memories_async")
async def test_assemble_coach_context_async_skips_retrieval_when_content_types_empty(
    mock_retrieve_async, db, routing_user
):
    context = await assemble_coach_context_async(
        db,
        routing_user.id,
        query_text="hello",
        content_types=[],
    )

    mock_retrieve_async.assert_not_awaited()
    assert "Player Context" in context


@pytest.mark.asyncio
@patch("app.services.chat.context_assembler.retrieve_semantic_memories_async")
async def test_general_question_passes_pattern_content_types(
    mock_retrieve_async, db, routing_user
):
    mock_retrieve_async.return_value = []
    coach = ChessCoach()

    await coach.process_message(
        message="How can I improve my endgames?",
        user_id=routing_user.id,
        db=db,
    )

    mock_retrieve_async.assert_awaited_once_with(
        db,
        routing_user.id,
        "How can I improve my endgames?",
        content_types=["pattern"],
    )


@pytest.mark.asyncio
@patch("app.services.chat.context_assembler.retrieve_semantic_memories_async")
async def test_general_question_includes_coaching_content_type_for_keywords(
    mock_retrieve_async, db, routing_user
):
    mock_retrieve_async.return_value = []
    coach = ChessCoach()

    await coach.process_message(
        message="Do you remember our last session on rook endgames?",
        user_id=routing_user.id,
        db=db,
    )

    mock_retrieve_async.assert_awaited_once_with(
        db,
        routing_user.id,
        "Do you remember our last session on rook endgames?",
        content_types=["pattern", "coaching"],
    )


@pytest.mark.asyncio
@patch("app.services.chat.context_assembler.retrieve_semantic_memories_async")
async def test_small_talk_skips_semantic_retrieval(mock_retrieve_async, db, routing_user):
    coach = ChessCoach()

    await coach.process_message(
        message="Hello!",
        user_id=routing_user.id,
        db=db,
    )

    mock_retrieve_async.assert_not_awaited()
