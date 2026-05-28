"""Tests for P2-GV-04 coach handoff service."""
from datetime import datetime, timezone

import pytest

from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.games.coach_handoff_service import (
    STARTING_FEN,
    build_coach_handoff,
    build_suggested_message,
    resolve_handoff_fen,
)

SAMPLE_PGN = """[Event "Test"]
[White "player1"]
[Black "opponent1"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0"""


@pytest.fixture
def owner(db):
    user = User(
        supabase_user_id="handoff-user",
        chesscom_username="player1",
        email="handoff@example.com",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def analyzed_game(db, owner):
    game = Game(
        user_id=owner.id,
        chesscom_game_id="handoff-game-1",
        white_username="player1",
        black_username="opponent1",
        pgn=SAMPLE_PGN,
        is_analyzed=True,
        end_time=datetime.now(timezone.utc),
    )
    db.add(game)
    db.flush()

    analysis = GameAnalysis(
        game_id=game.id,
        user_color="white",
        user_acpl=25.0,
        opponent_acpl=30.0,
        accuracy_percentage=82.0,
        opening_acpl=20.0,
        middlegame_acpl=28.0,
        endgame_acpl=35.0,
        opening_name="Ruy Lopez",
        opening_eco="C60",
        evaluations=[
            {
                "move_number": 1,
                "move_san": "e4",
                "move_uci": "e2e4",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "fen_after": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "evaluation_cp": 30.0,
                "evaluation_change": 0.0,
                "classification": "best",
                "best_move_uci": "e2e4",
                "is_user_move": True,
            },
            {
                "move_number": 2,
                "move_san": "e5",
                "move_uci": "e7e5",
                "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "fen_after": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "evaluation_cp": 25.0,
                "evaluation_change": -5.0,
                "classification": "blunder",
                "best_move_uci": "c7c5",
                "is_user_move": False,
            },
        ],
        critical_positions=[],
        blunder_moves=[],
    )
    db.add(analysis)
    db.commit()
    db.refresh(game)
    return game


def test_build_coach_handoff_defaults_to_last_move(db, owner, analyzed_game):
    payload = build_coach_handoff(db, analyzed_game, owner)

    assert payload["game_id"] == analyzed_game.id
    assert payload["move_number"] == 2
    assert payload["move_san"] == "e5"
    assert payload["classification"] == "blunder"
    assert payload["opening_name"] == "Ruy Lopez"
    assert payload["user_color"] == "white"
    assert "blunder" in payload["suggested_message"]
    assert payload["fen"].startswith("rnbqkbnr/")


def test_build_coach_handoff_specific_move(db, owner, analyzed_game):
    payload = build_coach_handoff(db, analyzed_game, owner, move_number=1)

    assert payload["move_number"] == 1
    assert payload["move_san"] == "e4"
    assert payload["classification"] == "best"
    assert payload["fen"] == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_build_coach_handoff_unknown_move_raises(db, owner, analyzed_game):
    with pytest.raises(LookupError, match="Move 99 not found"):
        build_coach_handoff(db, analyzed_game, owner, move_number=99)


def test_resolve_handoff_fen_pgn_fallback(db, owner):
    game = Game(
        user_id=owner.id,
        chesscom_game_id="handoff-game-2",
        white_username="player1",
        black_username="opponent1",
        pgn=SAMPLE_PGN,
        is_analyzed=False,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    detail = build_coach_handoff(db, game, owner)

    assert detail["move_san"] == "a6"
    assert detail["classification"] is None
    assert detail["fen"] == STARTING_FEN or detail["fen"]


def test_build_suggested_message_for_opening_only():
    detail = {"analysis": {"opening_name": "Italian Game"}}
    message = build_suggested_message(detail, None)

    assert "Italian Game" in message


def test_resolve_handoff_fen_uses_fen_before():
    detail = {
        "game": {},
        "moves": [
            {
                "move_number": 3,
                "move_san": "Nf3",
                "fen_before": "custom-fen-before",
                "fen_after": "custom-fen-after",
            }
        ],
    }

    fen, move_ctx = resolve_handoff_fen(detail, 3)

    assert fen == "custom-fen-before"
    assert move_ctx["move_san"] == "Nf3"
