"""Tests for chat auto-position detection from the user's games.

Covers the "coach asks for FEN unnecessarily" fix: position-dependent chat
intents must auto-prime the session position from the user's most recent
game, and only fall back to asking when no usable position exists.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.game import Game
from app.models.user import User
from app.services.chat import ChatIntent
from app.services.chat.chess_coach import ChessCoach
from app.services.games.coach_handoff_service import resolve_latest_game_handoff

MIDDLEGAME_FEN = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


@pytest.fixture
def coach_user(db):
    user = User(
        email="auto-position@example.com",
        supabase_user_id="auto-position-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_game(
    db,
    user: User,
    *,
    suffix: str,
    fen: str | None = None,
    pgn: str | None = None,
    end_time: datetime | None = None,
) -> Game:
    game = Game(
        user_id=user.id,
        chesscom_game_id=f"auto-position-test-{suffix}",
        time_class="rapid",
        white_username="auto-position-tester",
        black_username="opponent",
        white_result="win",
        black_result="checkmated",
        winner="white",
        pgn=pgn,
        fen=fen,
        end_time=end_time or datetime.now(timezone.utc),
        is_analyzed=False,
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def _fake_analysis(best_move: str) -> SimpleNamespace:
    return SimpleNamespace(
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


def test_resolve_latest_game_handoff_uses_latest_game(db, coach_user):
    _create_game(
        db,
        coach_user,
        suffix="old",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        end_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    _create_game(db, coach_user, suffix="new", fen=MIDDLEGAME_FEN)

    handoff = resolve_latest_game_handoff(db, coach_user)

    assert handoff is not None
    assert handoff["fen"] == MIDDLEGAME_FEN


def test_resolve_latest_game_handoff_none_when_no_usable_position(db, coach_user):
    _create_game(db, coach_user, suffix="bare", fen=None, pgn=None)

    assert resolve_latest_game_handoff(db, coach_user) is None


def test_resolve_latest_game_handoff_none_without_games(db, coach_user):
    assert resolve_latest_game_handoff(db, coach_user) is None


def test_resolve_latest_game_handoff_uses_pgn_moves_when_fen_missing(db, coach_user):
    game = _create_game(
        db,
        coach_user,
        suffix="pgn-only",
        fen=None,
        pgn='[Event "Test"]\n\n1. e4 e5 2. Nf3 *',
    )
    assert game.pgn

    handoff = resolve_latest_game_handoff(db, coach_user)

    assert handoff is not None
    assert handoff["fen"] not in (None, "")
    assert handoff["fen"] != "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.mark.asyncio
async def test_analyze_request_auto_primes_position_from_latest_game(db, coach_user):
    _create_game(db, coach_user, suffix="latest", fen=MIDDLEGAME_FEN)

    coach = ChessCoach()
    coach.move_recommender.analyze_position = AsyncMock(
        return_value=_fake_analysis("Nf3")
    )

    response = await coach.process_message(
        message="Analyze my latest game position",
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.ANALYZE_POSITION
    called_fen = coach.move_recommender.analyze_position.await_args.kwargs["fen"]
    assert called_fen == MIDDLEGAME_FEN
    assert response.position_fen == MIDDLEGAME_FEN


@pytest.mark.asyncio
async def test_explain_request_auto_primes_position_from_latest_game(db, coach_user):
    _create_game(db, coach_user, suffix="latest", fen=MIDDLEGAME_FEN)

    coach = ChessCoach()
    coach.move_recommender.analyze_position = AsyncMock(
        return_value=_fake_analysis("Nf3")
    )

    response = await coach.process_message(
        message="Why did I play Nf3?",
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.EXPLAIN_MOVE
    called_fen = coach.move_recommender.analyze_position.await_args.kwargs["fen"]
    assert called_fen == MIDDLEGAME_FEN


@pytest.mark.asyncio
async def test_analyze_request_without_games_uses_friendly_boundary(db, coach_user):
    coach = ChessCoach()

    response = await coach.process_message(
        message="Analyze my latest game position",
        user_id=coach_user.id,
        db=db,
    )

    assert response.intent == ChatIntent.ANALYZE_POSITION
    assert "upload a PGN or enter a position" in response.message
    assert "provide the position in FEN notation" not in response.message
