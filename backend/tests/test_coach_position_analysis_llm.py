"""Tests for LLM-translated position analysis (issue C).

The position-analysis handler used to reply with a raw engine dump regardless
of the question. Doctrine: Stockfish provides the facts, the LLM translates
them into a coaching reply; the deterministic dump is the fallback only.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.user import User
from app.services.chat import ChatIntent
from app.services.chat.chess_coach import ChessCoach

FEN = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


@pytest.fixture
def coach_user(db):
    user = User(
        email="position-llm@example.com",
        supabase_user_id="position-llm-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _fake_analysis():
    return SimpleNamespace(
        candidate_moves=[
            SimpleNamespace(
                move="Qg5+",
                uci="d1g5",
                evaluation=4.61,
                mate_in=None,
                explanation="Creates a winning fork.",
                tactical_themes=[
                    SimpleNamespace(value="fork"),
                    SimpleNamespace(value="checkmate_threat"),
                ],
            ),
            SimpleNamespace(
                move="e4",
                uci="e2e4",
                evaluation=3.96,
                mate_in=None,
                explanation="Solid alternative.",
                tactical_themes=[],
            ),
        ],
        insights="White has a winning advantage. Activate your king.",
        to_dict=lambda: {"candidate_moves": ["Qg5+", "e4"]},
    )


def _stub_engine(coach: ChessCoach) -> None:
    coach.move_recommender.analyze_position = AsyncMock(return_value=_fake_analysis())


@pytest.mark.asyncio
async def test_position_analysis_translated_by_llm(db, coach_user):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "Your queen fork wins material — here's how to convert it."}
    )
    coach = ChessCoach(ai_client=mock_client)
    _stub_engine(coach)

    response = await coach.process_message(
        message="Analyze this position and tell me my plan",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.ANALYZE_POSITION
    assert response.used_llm is True
    assert response.position_fen == FEN
    assert response.analysis == {"candidate_moves": ["Qg5+", "e4"]}

    system_prompt = mock_client.chat_completion.await_args.kwargs["messages"][0]["content"]
    assert "## Position Analysis" in system_prompt
    assert f"position_fen: {FEN}" in system_prompt
    assert "Qg5+" in system_prompt
    assert "+3.96" in system_prompt
    assert "engine insight" in system_prompt


@pytest.mark.asyncio
async def test_position_analysis_prompt_answers_the_question(db, coach_user):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(return_value={"content": "Plan: ..."})
    coach = ChessCoach(ai_client=mock_client)
    _stub_engine(coach)

    await coach.process_message(
        message="Analyze this position and tell me my plan",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    system_prompt = mock_client.chat_completion.await_args.kwargs["messages"][0]["content"]
    assert 'Analyze this position and tell me my plan' in system_prompt


@pytest.mark.asyncio
async def test_position_analysis_llm_failure_uses_engine_template(db, coach_user):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        side_effect=RuntimeError("all providers down")
    )
    coach = ChessCoach(ai_client=mock_client)
    _stub_engine(coach)

    response = await coach.process_message(
        message="Analyze this position",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    assert response.used_llm is False
    assert response.fallback_used is True
    assert response.fallback_reason == "LLM provider unavailable"
    assert "all providers down" not in response.message
    assert "I've analyzed this position for you!" in response.message
    assert "Best Move" in response.message


@pytest.mark.asyncio
async def test_position_analysis_without_llm_uses_engine_template(db, coach_user):
    coach = ChessCoach()
    _stub_engine(coach)

    response = await coach.process_message(
        message="Analyze this position",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    assert response.used_llm is False
    assert response.fallback_used is False
    assert "I've analyzed this position for you!" in response.message
    assert "Checkmate Threat" in response.message
