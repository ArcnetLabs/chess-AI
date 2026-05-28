"""Tests for P2-GV-01 game detail service."""
from datetime import datetime, timezone

import pytest

from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.games.game_detail_service import get_game_detail

SAMPLE_PGN = """[Event "Test"]
[White "player1"]
[Black "opponent1"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0"""


@pytest.fixture
def owner(db):
    user = User(
        supabase_user_id="detail-user",
        chesscom_username="player1",
        email="detail@example.com",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def analyzed_game(db, owner):
    game = Game(
        user_id=owner.id,
        chesscom_game_id="detail-game-1",
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
                "fen_before": "start",
                "fen_after": "after",
                "evaluation_cp": 30.0,
                "evaluation_change": 0.0,
                "classification": "best",
                "best_move_uci": "e2e4",
                "is_user_move": True,
            }
        ],
        critical_positions=[],
        blunder_moves=[],
    )
    db.add(analysis)
    db.commit()
    db.refresh(game)
    return game


def test_get_game_detail_uses_persisted_evaluations(db, owner, analyzed_game):
    detail = get_game_detail(db, analyzed_game, owner)

    assert detail["game"]["id"] == analyzed_game.id
    assert detail["analysis"]["opening_name"] == "Ruy Lopez"
    assert len(detail["moves"]) == 1
    assert detail["moves"][0]["classification"] == "best"
    assert detail["moves"][0]["phase"] == "opening"
    assert len(detail["phase_markers"]) == 3


def test_get_game_detail_pgn_fallback_without_evaluations(db, owner):
    game = Game(
        user_id=owner.id,
        chesscom_game_id="detail-game-2",
        white_username="player1",
        black_username="opponent1",
        pgn=SAMPLE_PGN,
        is_analyzed=False,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    detail = get_game_detail(db, game, owner)

    assert detail["analysis"] is None
    assert len(detail["moves"]) == 6
    assert detail["moves"][0]["move_san"] == "e4"
    assert detail["moves"][0]["evaluation_cp"] is None
    assert all(marker["phase"] in {"opening", "middlegame", "endgame"} for marker in detail["phase_markers"])
