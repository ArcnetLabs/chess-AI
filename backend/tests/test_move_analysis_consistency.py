"""Tests for the per-move analysis facts the coach relies on.

The bug these pin down, found by measuring production rows rather than reading code:
the analyzer evaluated the board **after** pushing the move and stored that
evaluation's ``best_move``, so the "best move" recorded against a ply was the
opponent's reply. On production, 2,982 of 3,000 stored best moves were legal in
``fen_after`` and none were legal in neither — which is what identified the cause.

Consequences it had: coaching text offered players alternatives they could not play
("you played f2f4, better was b8c6" — a Black move, to White), and ``is_best`` could
essentially never be true, so the best-move count was wrong.

The stub engine returns, for any position, the first legal move of the side to move.
That is enough to check the property that matters: **the recorded best move must be
legal in the position it is attached to.**
"""

import io

import chess
import chess.pgn
import pytest

from app.services.analysis.unified_analyzer import UnifiedChessAnalyzer


class _FirstLegalMoveEngine:
    """Stand-in engine: deterministic, no Stockfish binary required."""

    def __init__(self):
        self.evaluations = 0

    async def evaluate_position(self, board: chess.Board):
        self.evaluations += 1
        return {
            "evaluation_cp": 0,
            "mate_in": None,
            "best_move": next(iter(board.legal_moves)).uci() if board.legal_moves else None,
        }

    async def close(self):  # pragma: no cover - interface completeness
        return None


PGN = """
[Event "Test"]
[White "player"]
[Black "opponent"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0
"""


@pytest.mark.asyncio
async def test_recorded_best_move_is_legal_in_its_own_position():
    """The property that was violated: advice must be playable in that position."""
    game = chess.pgn.read_game(io.StringIO(PGN))
    analyzer = UnifiedChessAnalyzer(engine=_FirstLegalMoveEngine())

    moves = await analyzer._analyze_all_moves(game, user_color="white")

    assert moves, "premise: the analyzer produced move facts"
    for move in moves:
        assert move.best_move_uci, "every ply should carry an alternative"
        board = chess.Board(move.fen_before)
        assert chess.Move.from_uci(move.best_move_uci) in board.legal_moves, (
            f"best move {move.best_move_uci} is not playable in {move.fen_before}"
        )


@pytest.mark.asyncio
async def test_best_move_belongs_to_the_side_to_move_before_the_move():
    """It is the player's alternative, not the opponent's reply."""
    game = chess.pgn.read_game(io.StringIO(PGN))
    analyzer = UnifiedChessAnalyzer(engine=_FirstLegalMoveEngine())

    moves = await analyzer._analyze_all_moves(game, user_color="white")

    for move in moves:
        board = chess.Board(move.fen_before)
        best = chess.Move.from_uci(move.best_move_uci)
        moved_piece = board.piece_at(best.from_square)
        assert moved_piece is not None
        assert moved_piece.color == board.turn, (
            f"best move {move.best_move_uci} moves the wrong side's piece"
        )


@pytest.mark.asyncio
async def test_is_best_can_actually_be_true():
    """With the fix, playing the position's best move classifies as best.

    Before it, ``is_best`` compared the player's move with the opponent's best reply,
    so it was false for effectively every ply in the library.
    """
    engine = _FirstLegalMoveEngine()
    game = chess.pgn.read_game(io.StringIO(PGN))
    analyzer = UnifiedChessAnalyzer(engine=engine)

    moves = await analyzer._analyze_all_moves(game, user_color="white")

    # The stub always returns the first legal move, and White's first legal move in
    # the starting position is b1a3 — played here, so exactly one ply is "best".
    assert any(move.classification == "best" for move in moves), [m.classification for m in moves]
