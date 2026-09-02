"""Tests for the chat-triggered 'analyze my game' flow (ANALYZE_GAME intent).

Covers issue #4: the coach must pull the user's latest analyzed game into the
LLM prompt, queue analysis when it is missing, and use the no-games boundary
message only when there is nothing to work with.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.chat import ChatIntent
from app.services.chat.chess_coach import ChessCoach
from app.services.chat.intent_classifier import IntentClassifier


@pytest.fixture
def coach_user(db):
    user = User(
        email="analyze-game@example.com",
        supabase_user_id="analyze-game-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_game(db, user: User, *, suffix: str, analyzed: bool) -> Game:
    game = Game(
        user_id=user.id,
        chesscom_game_id=f"analyze-game-test-{suffix}",
        time_class="rapid",
        white_username="analyze-game-tester",
        black_username="rival",
        white_result="win",
        black_result="checkmated",
        winner="white",
        pgn='[Event "Test"]\n\n1. e4 e5 2. Nf3 *',
        fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        end_time=datetime.now(timezone.utc),
        is_analyzed=analyzed,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    if analyzed:
        analysis = GameAnalysis(
            game_id=game.id,
            engine_version="stockfish-test",
            user_color="white",
            user_acpl=25.0,
            opponent_acpl=40.0,
            accuracy_percentage=88.4,
            blunders=2,
            mistakes=3,
            inaccuracies=5,
            opening_name="Italian Game",
            opening_eco="C50",
            opening_moves=10,
            opening_acpl=20.0,
            middlegame_acpl=30.0,
            critical_positions=[
                {"move": 14, "classification": "blunder", "san": "Qxf7?"}
            ],
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
    return game


def test_classifier_routes_analyze_game_requests():
    classifier = IntentClassifier()

    for text in (
        "Analyze my latest game",
        "analyze my game",
        "Review my last game",
        "How did I do in my recent game?",
    ):
        intent, _ = classifier.classify(text)
        assert intent == ChatIntent.ANALYZE_GAME, text

    # Position requests must keep their existing, more specific intent.
    intent, _ = classifier.classify("Analyze this position")
    assert intent == ChatIntent.ANALYZE_POSITION


@pytest.mark.asyncio
async def test_analyze_game_uses_llm_with_game_facts(db, coach_user):
    game = _create_game(db, coach_user, suffix="analyzed", analyzed=True)
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        return_value={"content": "Your Italian Game was solid; the two blunders decided it."}
    )
    coach = ChessCoach(ai_client=mock_client)

    response = await coach.process_message(
        message="Analyze my latest game",
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.ANALYZE_GAME
    assert response.used_llm is True
    system_prompt = mock_client.chat_completion.await_args.kwargs["messages"][0]["content"]
    assert "## Latest Game Analysis" in system_prompt
    assert "Italian Game" in system_prompt
    assert "88.4" in system_prompt
    assert f"game_id: {game.id}" in system_prompt
    assert response.analysis["game_id"] == game.id


@pytest.mark.asyncio
async def test_analyze_game_queues_missing_analysis(db, coach_user):
    game = _create_game(db, coach_user, suffix="unanalyzed", analyzed=False)
    coach = ChessCoach()

    with patch("app.tasks.analysis_tasks.analyze_batch_games_task") as mock_task:
        mock_task.delay.return_value = MagicMock(id="celery-1")
        response = await coach.process_message(
            message="Analyze my latest game",
            user_id=coach_user.id,
            db=db,
        )

    assert response.intent == ChatIntent.ANALYZE_GAME
    assert "queued" in response.message.lower()
    assert response.analysis["game_id"] == game.id
    assert response.analysis["queue_status"] == "queued"
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_game_without_games_uses_boundary(db, coach_user):
    coach = ChessCoach()

    response = await coach.process_message(
        message="Analyze my latest game",
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.ANALYZE_GAME
    assert "don't have access to your recent games" in response.message


@pytest.mark.asyncio
async def test_analyze_game_llm_failure_uses_summary_template(db, coach_user):
    _create_game(db, coach_user, suffix="analyzed", analyzed=True)
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(
        side_effect=RuntimeError("all providers down")
    )
    coach = ChessCoach(ai_client=mock_client)

    response = await coach.process_message(
        message="Analyze my latest game",
        user_id=coach_user.id,
        db=db,
    )

    assert response.used_llm is False
    assert response.fallback_used is True
    assert "all providers down" not in response.message
    assert "I've reviewed your most recent game" in response.message
