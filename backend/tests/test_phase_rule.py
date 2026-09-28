"""Tests for the material-aware phase rule.

The rule, and why it is split:

* **The opening is decided by move count.** It is theory; material says nothing about
  whether you are still in it.
* **Everything after that is decided by material.** The old rule called a position an
  endgame once enough moves had been played, whatever was on the board — measured on a
  real player, that relabelled 27% of 8,599 rows, including 1,905 positions with queens
  on and material not simplified.

`simplified` is the existing material notion (both sides at or below the endgame
threshold), so a queen ending counts as an endgame — which is correct.
"""

import chess

from app.services.analysis.phase_boundaries import phase_for_move, phase_for_position


def features(*, simplified: bool) -> dict:
    return {"simplified": simplified, "material_band": "level"}


class TestOpeningStaysByMoveCount:
    def test_the_opening_keeps_counts(self):
        # Plenty of material, early move: still the opening.
        assert (
            phase_for_position(4, 80, features(simplified=False)) == "opening"
        )

    def test_an_early_mass_trade_does_not_end_the_opening(self):
        """Queens off on move 3 is still theory, not an endgame."""
        assert phase_for_position(4, 80, features(simplified=True)) == "opening"


class TestEndgameByMaterial:
    def test_a_queenless_ending_after_many_moves_is_an_endgame(self):
        assert phase_for_position(60, 80, features(simplified=True)) == "endgame"

    def test_full_material_late_in_the_game_is_not_an_endgame(self):
        """The case the old rule got wrong: move 40 with everything still on."""
        assert phase_for_position(60, 80, features(simplified=False)) == "middlegame"

    def test_simplified_early_is_an_endgame(self):
        """A queen ending reached on move 20 is an endgame, not a middlegame."""
        assert phase_for_position(40, 80, features(simplified=True)) == "endgame"


class TestAgainstRealPositions:
    def test_the_start_position_is_the_opening(self):
        board = chess.Board()
        from app.services.analysis.position_features import extract_features, is_simplified

        assert is_simplified(board) is False
        assert phase_for_position(1, 80, extract_features(board)) == "opening"

    def test_a_bare_king_and_pawn_ending_is_an_endgame(self):
        from app.services.analysis.position_features import extract_features, is_simplified

        board = chess.Board("8/5pk1/6p1/8/8/6P1/5PK1/8 w - - 0 40")
        assert is_simplified(board) is True
        assert phase_for_position(60, 80, extract_features(board)) == "endgame"

    def test_a_full_middlegame_position_is_a_middlegame(self):
        from app.services.analysis.position_features import extract_features, is_simplified

        board = chess.Board("r1bqkb1r/pp2pppp/2n2n2/3p4/3P4/2N2N2/PP2PPPP/R1BQKB1R w KQkq - 0 7")
        assert is_simplified(board) is False
        assert phase_for_position(40, 80, extract_features(board)) == "middlegame"

    def test_a_queen_ending_is_an_endgame(self):
        """Queens on the board, nothing else: still an endgame, by material."""
        from app.services.analysis.position_features import extract_features, is_simplified

        board = chess.Board("8/8/4k3/8/8/4K3/8/3Q3q w - - 0 40")
        assert is_simplified(board) is True
        assert phase_for_position(60, 80, extract_features(board)) == "endgame"


class TestCompatibility:
    def test_the_move_number_rule_is_unchanged_for_other_consumers(self):
        """Legacy detectors and the game-detail view still use the move-count rule."""
        assert phase_for_move(5, 80) == "opening"
        assert phase_for_move(60, 80) == "endgame"
