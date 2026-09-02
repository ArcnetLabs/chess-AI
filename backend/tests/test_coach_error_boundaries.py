"""Tests for coach error boundaries: friendly failures, never raw errors.

Covers the "image input errors surface raw model errors" fix: engine/LLM
exceptions in the position-dependent handlers must map to user-friendly
messages, with a dedicated catch for image/vision-unsupported model errors.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.chat import ChatIntent
from app.services.chat.chess_coach import ChessCoach

FEN = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


@pytest.fixture
def coach():
    return ChessCoach()


def _stub_analysis(coach: ChessCoach, best_move: str = "Nf3") -> None:
    coach.move_recommender.analyze_position = AsyncMock(
        return_value=SimpleNamespace(
            candidate_moves=[
                SimpleNamespace(
                    move=best_move,
                    uci=best_move,
                    evaluation=0.3,
                    mate_in=None,
                    explanation="Develops toward the center.",
                    tactical_themes=[],
                )
            ],
            insights="A calm developing move.",
            to_dict=lambda: {"candidate_moves": []},
        )
    )


@pytest.mark.asyncio
async def test_image_unsupported_error_becomes_feature_unavailable(coach):
    """'does not support image input' style failures must not reach the player raw."""
    _stub_analysis(coach)
    coach.move_recommender.analyze_position = AsyncMock(
        side_effect=RuntimeError("Model does not support image input")
    )

    response = await coach.process_message(
        message="Analyze this position",
        position_fen=FEN,
    )

    assert response.intent == ChatIntent.ANALYZE_POSITION
    assert response.message == "This feature isn't available yet."


@pytest.mark.asyncio
async def test_engine_timeout_gets_guided_retry_message(coach):
    _stub_analysis(coach)
    coach.move_recommender.analyze_position = AsyncMock(
        side_effect=TimeoutError("Stockfish analysis timed out")
    )

    response = await coach.process_message(
        message="Analyze this position",
        position_fen=FEN,
    )

    assert "taking longer than expected" in response.message
    assert "simpler position" in response.message
    assert "TimeoutError" not in response.message


@pytest.mark.asyncio
async def test_generic_engine_failure_hides_raw_error(coach):
    _stub_analysis(coach)
    coach.move_recommender.analyze_position = AsyncMock(
        side_effect=RuntimeError("engine pool exhausted: secret details xyz")
    )

    response = await coach.process_message(
        message="Analyze this position",
        position_fen=FEN,
    )

    assert response.message == (
        "I had trouble with that analysis. Please try again in a moment."
    )
    assert "secret details" not in response.message


@pytest.mark.asyncio
async def test_compare_moves_failure_hides_raw_error(coach):
    coach.move_recommender.compare_moves = AsyncMock(
        side_effect=RuntimeError("Model does not support image input")
    )

    response = await coach.process_message(
        message="Compare e4 and d4",
        position_fen=FEN,
    )

    assert response.intent == ChatIntent.COMPARE_MOVES
    assert response.message == "This feature isn't available yet."


@pytest.mark.asyncio
async def test_explain_move_failure_hides_raw_error(coach):
    _stub_analysis(coach, best_move="e4")
    coach.move_recommender.analyze_position = AsyncMock(
        side_effect=TimeoutError("timed out after 30s")
    )

    response = await coach.process_message(
        message="Why did I play e4?",
        position_fen=FEN,
    )

    assert response.intent == ChatIntent.EXPLAIN_MOVE
    assert "taking longer than expected" in response.message
    assert "timed out after 30s" not in response.message
