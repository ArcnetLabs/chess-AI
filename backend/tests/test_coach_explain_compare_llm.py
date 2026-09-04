"""Tests for LLM-translated move explanations and comparisons (issue C follow-up).

Both handlers previously replied with deterministic dumps; per the repo
doctrine (Stockfish = truth, LLM = translation layer) they now ground the
question-aware LLM reply in the engine facts, falling back to the original
templates only when no AI client is configured or the provider chain fails.
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
        email="explain-compare@example.com",
        supabase_user_id="explain-compare-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _fake_analysis(best_move: str) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_moves=[
            SimpleNamespace(
                move=best_move,
                uci=best_move,
                evaluation=0.3,
                mate_in=None,
                explanation="Develops toward the center.",
                tactical_themes=[SimpleNamespace(value="development")],
                pros=["Develops a piece", "Controls e4"],
                cons=["No significant drawbacks"],
                variations=[f"1. {best_move} Nc6 2. Bb5"],
                difficulty=SimpleNamespace(value="beginner"),
                to_dict=lambda: {"move": best_move},
            )
        ],
        insights="A calm developing move.",
        to_dict=lambda: {"candidate_moves": [best_move]},
    )


def _fake_comparison() -> dict:
    return {
        "comparisons": [
            {"move": "e4", "evaluation": 0.42, "mate_in": None},
            {"move": "d4", "evaluation": 0.31, "mate_in": None},
        ],
        "recommendation": "e4 keeps more attacking options open.",
    }


@pytest.mark.asyncio
async def test_explain_move_translated_by_llm(db, coach_user):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "Nf3 develops toward the center and keeps your options open."}
    )
    coach = ChessCoach(ai_client=mock_client)
    coach.move_recommender.analyze_position = AsyncMock(
        return_value=_fake_analysis("Nf3")
    )

    response = await coach.process_message(
        message="Why did I play Nf3 instead of developing my bishop?",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.EXPLAIN_MOVE
    assert response.used_llm is True
    assert "keeps your options open" in response.message

    system_prompt = mock_client.chat_completion.await_args.kwargs["messages"][0]["content"]
    assert "## Move Explanation" in system_prompt
    assert f"position_fen: {FEN}" in system_prompt
    assert "Nf3" in system_prompt
    assert "Develops toward the center." in system_prompt


@pytest.mark.asyncio
async def test_explain_move_llm_failure_uses_template(db, coach_user):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(side_effect=RuntimeError("providers down"))
    coach = ChessCoach(ai_client=mock_client)
    coach.move_recommender.analyze_position = AsyncMock(
        return_value=_fake_analysis("Nf3")
    )

    response = await coach.process_message(
        message="Why did I play Nf3 instead of developing my bishop?",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    assert response.used_llm is False
    assert response.fallback_used is True
    assert "providers down" not in response.message
    assert "Great question about **Nf3**!" in response.message


@pytest.mark.asyncio
async def test_compare_moves_translated_by_llm(db, coach_user):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "e4 is the sharper choice here — here's why."}
    )
    coach = ChessCoach(ai_client=mock_client)
    coach.move_recommender.compare_moves = AsyncMock(
        return_value=_fake_comparison()
    )

    response = await coach.process_message(
        message="Compare e4 and d4",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.COMPARE_MOVES
    assert response.used_llm is True
    assert "sharper choice" in response.message

    system_prompt = mock_client.chat_completion.await_args.kwargs["messages"][0]["content"]
    assert "## Move Comparison" in system_prompt
    assert f"position_fen: {FEN}" in system_prompt
    assert "e4: Slight edge (+0.42)" in system_prompt
    assert "engine recommendation" in system_prompt


@pytest.mark.asyncio
async def test_compare_moves_llm_failure_uses_template(db, coach_user):
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(side_effect=RuntimeError("providers down"))
    coach = ChessCoach(ai_client=mock_client)
    coach.move_recommender.compare_moves = AsyncMock(
        return_value=_fake_comparison()
    )

    response = await coach.process_message(
        message="Compare e4 and d4",
        position_fen=FEN,
        user_id=coach_user.id,
        db=db,
    )

    assert response.used_llm is False
    assert response.fallback_used is True
    assert "providers down" not in response.message
    # extract_moves dedupes through a set, so move order is not guaranteed.
    assert any(
        f"Comparing {pair}" in response.message
        for pair in ("e4, d4", "d4, e4")
    )
