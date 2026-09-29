"""Per-move evaluation frames: ACPL must be the mover's own loss.

``StockfishEngine.evaluate_position`` returns ``score.relative`` — POV of the
side to move, which alternates every ply. The analyzer used to flip the running
``prev_cp`` in place, so from the second black move on each ply was compared
against an evaluation in the opposite frame and the "loss" came out at roughly
twice the evaluation itself.

Live evidence (game 2535, user playing Black): stored ACPL 865.4, 26 "blunders",
0.0% accuracy — where the per-move cp_loss rows say ACPL 29.6, 1 blunder, 90.2%.
Across 48 games the mean ACPL was 315.1 instead of 75.9 and the mean accuracy
38.6% instead of 71.4%.
"""
from dataclasses import dataclass, field
from typing import List, Optional

import pytest

from app.services.analysis.move_facts import MATE_SCORE
from app.services.analysis.unified_analyzer import UnifiedChessAnalyzer


@dataclass
class _StubEval:
    """One canned engine answer, in the engine's own POV-of-side-to-move frame."""

    evaluation_cp: Optional[float]
    mate_in: Optional[int] = None
    best_move: Optional[str] = None
    pv: List[str] = field(default_factory=list)


class _StubEngine:
    """Returns a fixed sequence of evaluations, one per ``evaluate_position``."""

    def __init__(self, evals: List[_StubEval]):
        self._evals = list(evals)
        self._index = 0
        self.depth = 14
        self.calls = 0

    async def evaluate_position(self, board):
        self.calls += 1
        if self._index >= len(self._evals):
            raise AssertionError("stub engine ran out of canned evaluations")
        item = self._evals[self._index]
        self._index += 1
        return {
            "evaluation_cp": item.evaluation_cp,
            "mate_in": item.mate_in,
            "best_move": item.best_move,
            "pv": item.pv,
        }

    def is_initialized(self) -> bool:
        return True


def _pgn(moves: str) -> str:
    return (
        '[Event "Test"]\n[White "white"]\n[Black "black"]\n[Result "*"]\n\n'
        f"{moves} *\n"
    )


@pytest.mark.asyncio
async def test_acpl_uses_the_movers_own_frame_for_both_colors():
    """Two plies, one per color, with hand-computed losses.

    Engine answers (POV of the side to move *after* the move):

    * initial position : +40 (White to move, so White is +40)
    * after 1. e4      : -20 (Black to move, so Black is -20 -> White +20)
    * after 1... e5    : +30 (White to move, so White is +30)

    White gave up 40 - 20 = 20; Black gave up 20 - 30 = 10. The old code, which
    flipped the running value in place, produced 60 and 50.
    """
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=40.0, best_move="e2e4"),
            _StubEval(evaluation_cp=-20.0, best_move="e7e5"),
            _StubEval(evaluation_cp=30.0, best_move="g1f3"),
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn("1. e4 e5"), user_color="white", game_id=1
    )

    assert result is not None
    assert result.user_acpl == pytest.approx(20.0)
    assert result.opponent_acpl == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_loss_is_never_negative_and_ignores_improving_moves():
    """A move that gains evaluation is not a loss.

    White was +30 and is +50 afterwards (the engine, to move for Black, says
    -50). White gave up nothing, so White's ACPL is 0 rather than 20.
    """
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=30.0, best_move="e2e4"),
            _StubEval(evaluation_cp=-50.0, best_move="e7e5"),
            _StubEval(evaluation_cp=50.0, best_move="g1f3"),
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn("1. e4 e5"), user_color="white", game_id=2
    )

    assert result is not None
    assert result.user_acpl == pytest.approx(0.0)
    white_moves = [m for m in result.all_moves if m.is_user_move]
    assert [m.classification for m in white_moves] == ["best"]


@pytest.mark.asyncio
async def test_a_lopsided_but_stable_position_is_not_a_game_of_blunders():
    """The production regression, in its purest form.

    White is a rook up and stays a rook up. Every engine answer alternates
    sign purely because the side to move alternates: +600 with White to move,
    -600 with Black to move. Nobody lost anything, so ACPL must be 0.

    Mixing frames turned that 600-point advantage into a ~1200cp "loss" on
    every single ply: game 2535 reported ACPL 865 with 26 blunders and 0.0%
    accuracy for a player whose moves lost 30cp on average.
    """
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=600.0, best_move="e2e4"),   # White to move
            _StubEval(evaluation_cp=-600.0, best_move="e7e5"),  # Black to move
            _StubEval(evaluation_cp=600.0, best_move="g1f3"),   # White to move
            _StubEval(evaluation_cp=-600.0, best_move="g8f6"),  # Black to move
            _StubEval(evaluation_cp=600.0, best_move="f1b5"),   # White to move
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn("1. e4 e5 2. Nf3 Nf6"), user_color="black", game_id=3
    )

    assert result is not None
    assert result.user_acpl == pytest.approx(0.0)
    assert result.opponent_acpl == pytest.approx(0.0)
    assert result.blunders == 0
    assert result.mistakes == 0
    assert result.inaccuracies == 0
    assert result.accuracy_percentage == pytest.approx(99.0)


@pytest.mark.asyncio
async def test_a_real_blunder_is_measured_once():
    """Black was 50 down, then 600 down: one 550cp loss, one blunder.

    The evaluation swing belongs to Black's move alone — it is not added to
    White's move as well, which is what comparing across frames did. Black's
    second move gives nothing back, so Black's ACPL is the 550 spread over the
    two moves Black played.
    """
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=50.0, best_move="e2e4"),    # White to move
            # The position Black faces: the engine wants 1...Nf6, not 1...d5.
            _StubEval(evaluation_cp=-50.0, best_move="g8f6"),
            _StubEval(evaluation_cp=600.0, best_move="g1f3"),   # White to move
            _StubEval(evaluation_cp=-600.0, best_move="g8f6"),  # Black to move
            _StubEval(evaluation_cp=600.0, best_move="f1b5"),   # White to move
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn("1. e4 d5 2. Nf3 Nf6"), user_color="black", game_id=6
    )

    assert result is not None
    # Black's two moves: the 550cp blunder and a holding move that lost nothing.
    assert result.user_acpl == pytest.approx(275.0)
    assert result.blunders == 1
    assert result.opponent_acpl == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_mate_positions_are_bounded_and_signed_for_the_mover():
    """Mate is decisive, bounded, and never counted as an improving move.

    ``evaluation_cp`` is ``None`` in a mate, so the sign has to come from
    ``mate_in``, which is reported for the side to move *after* the move.
    """
    engine = _StubEngine(
        [
            # The engine's own choice is 1. d4, so 1. e4 is judged on its loss
            # rather than being short-circuited by an "is the best move" flag.
            _StubEval(evaluation_cp=20.0, best_move="d2d4"),
            # White's move leaves Black mating in 2 -> Black POV +MATE.
            _StubEval(evaluation_cp=None, mate_in=2, best_move="e7e5"),
            # Black delivers the mate -> White (to move) is mated -> -MATE.
            _StubEval(evaluation_cp=None, mate_in=-1, best_move="d8h4"),
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn("1. e4 e5"), user_color="white", game_id=4
    )

    assert result is not None
    white_moves = [m for m in result.all_moves if m.is_user_move]
    assert len(white_moves) == 1
    # White was +20 and is now getting mated: bounded at MATE_SCORE, not
    # unbounded, and the sign says "this cost White the game".
    assert white_moves[0].evaluation_change == pytest.approx(MATE_SCORE + 20.0)
    assert white_moves[0].classification == "blunder"


@pytest.mark.asyncio
async def test_evaluation_cp_stays_black_centric_for_downstream_readers():
    """``move_facts`` reads ``evaluation_cp`` as black-centric; keep that true."""
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=40.0, best_move="e2e4"),
            _StubEval(evaluation_cp=-20.0, best_move="e7e5"),  # Black POV
            _StubEval(evaluation_cp=10.0, best_move="g1f3"),   # White POV
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn("1. e4 e5"), user_color="white", game_id=5
    )

    assert result is not None
    first, second = result.all_moves[0], result.all_moves[1]
    # Ply 1 is White's move: the stored value is the engine's, already Black's POV.
    assert first.evaluation_cp == pytest.approx(-20.0)
    # Ply 2 is Black's move: the engine returned White's POV, so it is negated.
    assert second.evaluation_cp == pytest.approx(-10.0)
