"""Tests for per-sentence intent classification (issue B: false routing).

The production incident: "Okay, what patterns are you noticing that you think
i should be aware of?...do i play aggressively and lean into that or what?"
matched the whole-message pattern ``what.*should.*do`` ACROSS the sentence
boundary and was routed to Stockfish position analysis instead of the
grounded coaching path.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.user import User
from app.services.chat import ChatIntent
from app.services.chat.chess_coach import ChessCoach
from app.services.chat.intent_classifier import IntentClassifier


@pytest.fixture
def classifier():
    return IntentClassifier()


@pytest.fixture
def coach_user(db):
    user = User(
        email="intent-sentences@example.com",
        supabase_user_id="intent-sentences-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


PROD_INCIDENT_MESSAGE = (
    "Okay, what patterns are you noticing that you think i should be aware "
    "of?...do i play aggressively and lean into that or what?"
)


def test_prod_incident_message_not_routed_to_engine_handlers(classifier):
    """The exact production message must not hit a Stockfish-dump intent."""
    intent, confidence = classifier.classify(PROD_INCIDENT_MESSAGE)

    assert intent not in {
        ChatIntent.ANALYZE_POSITION,
        ChatIntent.ANALYZE_GAME,
        ChatIntent.EXPLAIN_MOVE,
        ChatIntent.COMPARE_MOVES,
    }


def test_cross_sentence_pattern_question_uses_first_sentence(classifier):
    """A question spanning two sentences keeps the intent of the first one."""
    intent, confidence = classifier.classify(
        "What patterns do you see in my games? What should I do about it?"
    )

    assert intent == ChatIntent.GENERAL_QUESTION
    assert confidence == 0.9


def test_leading_filler_routes_personal_coaching_question(classifier):
    intent, confidence = classifier.classify(
        "Okay, what's holding me back from 1800?"
    )

    assert intent == ChatIntent.GENERAL_QUESTION
    assert confidence == 0.45


def test_greeting_then_request_routes_to_request(classifier):
    intent, _ = classifier.classify("Hi. Analyze my game")

    assert intent == ChatIntent.ANALYZE_GAME


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Hello!", ChatIntent.SMALL_TALK),
        ("hey, how are you", ChatIntent.SMALL_TALK),
        ("Analyze this position", ChatIntent.ANALYZE_POSITION),
        ("Why did I play e4?", ChatIntent.EXPLAIN_MOVE),
        ("Compare e4 and d4", ChatIntent.COMPARE_MOVES),
        ("What patterns do you see in my games?", ChatIntent.GENERAL_QUESTION),
        ("What's holding me back from 1800?", ChatIntent.GENERAL_QUESTION),
    ],
)
def test_single_sentence_intents_unchanged(classifier, message, expected):
    intent, _ = classifier.classify(message)
    assert intent == expected


@pytest.mark.asyncio
async def test_prod_incident_message_reaches_llm_not_stockfish(db, coach_user):
    """End-to-end: the incident message must go to the LLM, never to the engine dump."""
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={
            "content": "Your data points to consistent opening drift rather than style."
        }
    )
    coach = ChessCoach(ai_client=mock_client)
    coach.move_recommender.analyze_position = AsyncMock()
    coach.move_recommender.compare_moves = AsyncMock()

    response = await coach.process_message(
        message=PROD_INCIDENT_MESSAGE,
        user_id=coach_user.id,
        db=db,
    )

    assert response.used_llm is True
    assert "Best Move" not in response.message
    coach.move_recommender.analyze_position.assert_not_awaited()
    coach.move_recommender.compare_moves.assert_not_awaited()
    mock_client.chat_completion.assert_awaited_once()
