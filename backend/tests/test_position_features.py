"""Tests for deterministic position features and move-fact derivation.

These guard the two properties everything downstream depends on: position keys
that identify a position regardless of move order, and centipawn loss computed
in the mover's own perspective (the old ``evaluation_change`` mixed them).
"""

import chess
import pytest

from app.services.analysis.move_facts import (
    MATE_SCORE,
    build_move_facts,
)
from app.services.analysis.position_features import (
    ENDGAME_MATERIAL_THRESHOLD,
    extract_features,
    hanging_pieces,
    is_simplified,
    material_balance,
    position_key,
    structure_key,
)

START_FEN = chess.STARTING_FEN


class Move:
    """Stand-in for ``MoveAnalysis`` (only the fields move_facts reads)."""

    def __init__(
        self,
        *,
        fen_before: str,
        fen_after: str,
        evaluation_cp,
        mate_in=None,
        move_uci="e2e4",
        move_san="e4",
        best_move_uci="e2e4",
        classification="good",
        is_user_move=True,
        pv=None,
    ):
        self.fen_before = fen_before
        self.fen_after = fen_after
        self.evaluation_cp = evaluation_cp
        self.mate_in = mate_in
        self.move_uci = move_uci
        self.move_san = move_san
        self.best_move_uci = best_move_uci
        self.classification = classification
        self.is_user_move = is_user_move
        self.pv = pv


class TestPositionKeys:
    def test_same_position_different_move_order_shares_a_key(self):
        """Transpositions must collide: 1.Nf3 d5 2.d4 and 1.d4 d5 2.Nf3."""
        first = chess.Board()
        for san in ("Nf3", "d5", "d4"):
            first.push_san(san)

        second = chess.Board()
        for san in ("d4", "d5", "Nf3"):
            second.push_san(san)

        assert first.fen() != second.fen()  # clocks differ
        assert position_key(first) == position_key(second)

    def test_different_positions_have_different_keys(self):
        board = chess.Board()
        other = chess.Board()
        other.push_san("e4")
        assert position_key(board) != position_key(other)

    def test_structure_key_ignores_piece_placement(self):
        """A pawn skeleton key should match when only pieces have moved."""
        first = chess.Board()
        first.push_san("e4")
        second = chess.Board()
        second.push_san("Nf3")
        third = chess.Board()
        third.push_san("e4")
        # Different pawn structures differ.
        assert structure_key(first) != structure_key(second)
        # Same pawn structure, same side to move, same key.
        assert structure_key(first) == structure_key(third)


class TestMaterialAndFeatures:
    def test_start_position_is_level(self):
        assert material_balance(chess.Board()) == 0

    def test_material_balance_sign_follows_white(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        board.remove_piece_at(chess.A8)  # black loses a rook
        assert material_balance(board) == 500

    def test_hanging_pieces_finds_undefended_piece(self):
        # Black queen on d5, attacked by the white pawn on c4 and undefended.
        board = chess.Board("rnb1kbnr/ppp1pppp/8/3q4/2P5/8/PP1PPPPP/RNBQKBNR w KQkq - 0 1")
        assert "d5" in hanging_pieces(board, chess.BLACK)

    def test_features_are_expressed_from_the_mover_perspective(self):
        board = chess.Board()
        board.remove_piece_at(chess.A8)  # White is a rook up
        as_white = extract_features(board, mover=chess.WHITE)
        as_black = extract_features(board, mover=chess.BLACK)
        assert as_white["material_balance"] == 500
        assert as_black["material_balance"] == -500
        assert as_white["material_band"] == "clear"

    def test_simplified_detects_endgame_material(self):
        assert not is_simplified(chess.Board())
        endgame = chess.Board("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
        assert is_simplified(endgame)
        assert ENDGAME_MATERIAL_THRESHOLD > 0


class TestMoveFactEvaluationMath:
    def test_evaluation_cp_is_black_centric_and_loss_is_mover_centric(self):
        """A white move that drops the eval must show a positive loss for White.

        The analyzer stores ``evaluation_cp`` black-centric, so a value that
        moves from 0 to +300 means White got *worse* by 300.
        """
        rows = build_move_facts(
            user_id=1,
            game_id=1,
            user_color="white",
            moves=[
                Move(
                    fen_before=START_FEN,
                    fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    evaluation_cp=0,
                ),
                Move(
                    fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    fen_after="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    evaluation_cp=0,
                ),
                Move(
                    fen_before="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    fen_after="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    evaluation_cp=300,  # Black-centric: White is now 300 worse
                    classification="blunder",
                ),
            ],
        )

        assert rows[0]["color"] == "white"
        assert rows[1]["color"] == "black"
        third = rows[2]
        # White's own eval went from 0 to -300 in White's perspective.
        assert third["eval_before_cp"] == pytest.approx(0.0, abs=1.0)
        assert third["eval_after_cp"] == pytest.approx(-300.0, abs=1.0)
        assert third["cp_loss"] == pytest.approx(300.0, abs=1.0)

    def test_black_mover_loss_uses_black_perspective(self):
        rows = build_move_facts(
            user_id=1,
            game_id=1,
            user_color="black",
            moves=[
                Move(
                    fen_before=START_FEN,
                    fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    evaluation_cp=0,
                ),
                Move(
                    fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    fen_after="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    evaluation_cp=-250,  # Black-centric: Black is 250 worse
                ),
            ],
        )
        black_move = rows[1]
        assert black_move["cp_loss"] == pytest.approx(250.0, abs=1.0)

    def test_mate_is_not_scored_as_a_quiet_position(self):
        """Walking into mate must not look like a 0 cp loss."""
        rows = build_move_facts(
            user_id=1,
            game_id=1,
            user_color="white",
            moves=[
                Move(
                    fen_before=START_FEN,
                    fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    evaluation_cp=0,
                ),
                Move(
                    fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    evaluation_cp=0,
                ),
                Move(
                    fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    evaluation_cp=0,
                    mate_in=1,  # opponent mates
                    classification="blunder",
                ),
            ],
        )
        mate_move = rows[2]
        assert mate_move["is_mate_score"] is True
        assert mate_move["eval_after_cp"] == pytest.approx(-MATE_SCORE, abs=1.0)
        assert mate_move["cp_loss"] > 500
        # Bounded: one mate must not swamp centipawn statistics.
        assert MATE_SCORE <= 2000

    def test_rows_carry_identity_position_and_phase(self):
        rows = build_move_facts(
            user_id=7,
            game_id=42,
            user_color="white",
            moves=[
                Move(
                    fen_before=START_FEN,
                    fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                    evaluation_cp=0,
                )
            ],
        )
        row = rows[0]
        assert row["user_id"] == 7
        assert row["game_id"] == 42
        assert row["ply"] == 1
        assert row["move_number"] == 1
        assert row["is_user_move"] is True
        assert row["position_key"]
        assert row["structure_key"]
        assert row["phase"] == "opening"
        assert row["prev_ply"] is None
        assert row["features"]["material_balance"] == 0
