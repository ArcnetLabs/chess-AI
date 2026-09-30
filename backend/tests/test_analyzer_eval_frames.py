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

The frame contract, stated once
-------------------------------
Let ``s(n)`` be the engine's answer *after* ply ``n`` (POV of the side to move
there, mate-bounded, ``s(0)`` the initial position). The mover of ply ``n`` is
the side to move in the position *before* it, so their loss is
``max(0, s(n-1) - (-s(n)))``: that is, ``max(0, s(n-1) + s(n))``. Every test
below is arithmetic on that definition.

The second half of the same bug (user 34, 50 analysed games) was the *carry*
between plies. ``prev_cp`` was overwritten at the end of the loop with the
black-centric stored value, mates flattened to 0, which is the next mover's own
frame only when the ply just played was White's — so Black's moves (even plies,
always preceded by a White ply) were right while every one of White's moves from
ply 3 on was compared against a black-centric evaluation. Stored ACPL missed
``game_moves.cp_loss`` by 223.0cp on average across the 25 White games (0 of 25
within 1cp) against 15.9cp for the 24 Black games (18 of 24), and all 8 games
recorded at 0.0% accuracy were White. The tests below are the White path the
older ones missed.
"""
from dataclasses import dataclass, field
from typing import List, Optional

import pytest

from app.services.analysis.move_facts import MATE_SCORE, build_move_facts
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


# 6 plies, 3 moves each: enough for White to have moves at plies 3 and 5, which
# is where the carry bug lived (White's own moves are the odd plies, and only
# the first of them is preceded by the initial position rather than by a Black
# ply whose cached value was in the wrong frame).
SIX_MOVES = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"


@pytest.mark.asyncio
async def test_white_players_losses_are_measured_in_his_own_frame():
    """The production regression on the White side, in its purest form.

    White loses 1. e4 outright and is lost for the rest of the game, playing
    steadily from there. The stored evaluations alternate sign purely because
    the side to move alternates, so the position is -300 with Black to move and
    +300 with White to move — the same position.

    Engine answers, in the side-to-move frame of the position each was taken in
    (so the sign flips at every ply even though nothing is happening):

    * s(0) = +40 (White to move, White's own evaluation)
    * s(1) = +300, s(2) = -300  -> White -300 after 1. e4
    * s(3) = +310, s(4) = -310  -> White -310
    * s(5) = +320, s(6) = -320  -> White -320

    In the mover's frame: White's moves are 40 -> 300 (340 lost), 300 -> 310 (10)
    and 310 -> 320 (10), so White's ACPL is (340 + 10 + 10) / 3 = 120.0. Black
    never gives anything back at all, so Black's is 0.0.

    The buggy carry negated the *previous* value for White's moves from ply 3,
    reading 310 and 320 as gains of 610 and 630 and reporting an ACPL of 526.7
    with 0.0% accuracy for a player who lost 120cp a move.
    """
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=40.0, best_move="d2d4"),   # initial, White
            _StubEval(evaluation_cp=300.0),                    # after 1. e4, Black POV
            _StubEval(evaluation_cp=-300.0),                   # after 1... e5, White POV
            _StubEval(evaluation_cp=310.0),                    # after 2. Nf3, Black POV
            _StubEval(evaluation_cp=-310.0),                   # after 2... Nc6, White POV
            _StubEval(evaluation_cp=320.0),                    # after 3. Bb5, Black POV
            _StubEval(evaluation_cp=-320.0),                   # after 3... a6, White POV
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn(SIX_MOVES), user_color="white", game_id=7
    )

    assert result is not None
    assert result.user_acpl == pytest.approx(120.0)
    assert result.opponent_acpl == pytest.approx(0.0)
    # acpl_to_accuracy(120) = 60 - (120 - 100) / 5. The bug pinned it to 0.0,
    # which is how 8 White games were stored as "0.0% accuracy".
    assert result.accuracy_percentage == pytest.approx(56.0)

    white_moves = [m for m in result.all_moves if m.is_user_move]
    assert [m.evaluation_change for m in white_moves] == pytest.approx([340.0, 10.0, 10.0])


@pytest.mark.asyncio
async def test_a_white_blunder_in_a_won_position_is_not_reported_as_zero():
    """The other direction: a real White loss read as no loss at all.

    White wins a rook (1. e4 takes the position to +420), then throws 370cp of
    it back with 2. Nf3, landing on +50 — still winning, but 370cp worse.

    Engine answers: s(0) = +40, s(1) = -420, s(2) = +420, s(3) = -50,
    s(4) = +50, s(5) = -50, s(6) = +50.

    White's moves: 40 -> 420 (nothing lost), 420 -> 50 (370 lost), 50 -> 50
    (nothing lost). ACPL = 370 / 3 = 123.33. The buggy carry made both of the
    last two read as ``max(0, -before + after)``, which is negative precisely
    when the player is winning, so a 370cp blunder was reported as 0.0 ACPL and
    99% accuracy — game 2730's shape (stored 3.7 against a cp_loss mean of 22.1).
    """
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=40.0),                    # initial, White POV
            _StubEval(evaluation_cp=-420.0),                  # after 1. e4, Black POV
            # The engine prefers 2. d4 here, so 2. Nf3 is judged on its loss
            # rather than short-circuited by "is this the best move".
            _StubEval(evaluation_cp=420.0, best_move="d2d4"),  # after 1... e5, White POV
            _StubEval(evaluation_cp=-50.0),                   # after 2. Nf3, Black POV
            _StubEval(evaluation_cp=50.0, best_move="a2a3"),  # after 2... Nc6, White POV
            _StubEval(evaluation_cp=-50.0),                   # after 3. Bb5, Black POV
            _StubEval(evaluation_cp=50.0),                    # after 3... a6, White POV
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn(SIX_MOVES), user_color="white", game_id=8
    )

    assert result is not None
    assert result.user_acpl == pytest.approx(370.0 / 3)
    assert result.opponent_acpl == pytest.approx(0.0)
    assert result.accuracy_percentage == pytest.approx(60.0 - (370.0 / 3 - 100) / 5)

    white_moves = [m for m in result.all_moves if m.is_user_move]
    assert [m.evaluation_change for m in white_moves] == pytest.approx([0.0, 370.0, 0.0])
    assert [m.classification for m in white_moves] == ["best", "blunder", "best"]
    assert result.blunders == 1


@pytest.mark.asyncio
async def test_a_mate_ply_carries_its_bounded_score_into_the_next_move():
    """A mate is bounded *and* carried; a carry of 0 charged it twice.

    White walks into a mate on move 2 and is then mated regardless of what is
    played, so nothing White does afterwards loses anything.

    Engine answers: s(0) = +40, s(1) = 0, s(2) = 0, then mates — s(3) = +MATE
    (Black mates in 3), s(4) = -MATE (White mated in 2), s(5) = +MATE (Black
    mates in 1), s(6) = -MATE.

    White's moves: 40 -> 0 in the opening (40 lost, White's real error is the
    first move here), 0 -> -MATE (1200 lost: walking into mate), and
    -MATE -> -MATE (nothing: already lost). ACPL = (40 + 1200 + 0) / 3 = 413.33.

    The stored centipawn value flattens a mate to 0, so carrying that instead of
    the bounded score made the third move read as a fresh 1200cp loss and
    reported 813.33 ACPL with a "blunder" on a move that changed nothing — the
    607-of-711 mate rows ``move_facts`` had to work around.
    """
    engine = _StubEngine(
        [
            _StubEval(evaluation_cp=40.0, best_move="e2e4"),
            _StubEval(evaluation_cp=0.0),                     # after 1. e4
            # The engine wants 1... e5 followed by 2. Nc3, not 2. Nf3.
            _StubEval(evaluation_cp=0.0, best_move="b1c3"),   # after 1... e5, White POV
            _StubEval(evaluation_cp=None, mate_in=3),         # after 2. Nf3: Black mates
            _StubEval(evaluation_cp=None, mate_in=-2),        # after 2... Nc6: White mated
            _StubEval(evaluation_cp=None, mate_in=1),         # after 3. Bb5: Black mates
            _StubEval(evaluation_cp=None, mate_in=-1),        # after 3... a6: White mated
        ]
    )
    analyzer = UnifiedChessAnalyzer(engine=engine)

    result = await analyzer.analyze_game(
        _pgn(SIX_MOVES), user_color="white", game_id=9
    )

    assert result is not None
    assert result.user_acpl == pytest.approx((40.0 + MATE_SCORE) / 3)
    assert result.opponent_acpl == pytest.approx(0.0)

    white_moves = [m for m in result.all_moves if m.is_user_move]
    assert [m.evaluation_change for m in white_moves] == pytest.approx(
        [40.0, MATE_SCORE, 0.0]
    )
    # A move that lost nothing, in a position that was already lost, is not a
    # blunder — the flattened carry said 1200.
    assert white_moves[2].classification == "best"


@pytest.mark.asyncio
async def test_acpl_is_the_mean_of_move_facts_cp_loss_for_both_colors():
    """The two layers must compute the same number, for both colours.

    ``game_moves.cp_loss`` is what the rest of the system treats as canonical
    and it is built from these same ``MoveAnalysis`` objects, so a player's ACPL
    has to be the mean of their own moves' ``cp_loss`` — the property the run at
    33 broke by 223.0cp for White while Black held at 15.9cp.

    The position slides from +40 to -700 in White's frame across a Ruy Lopez, so
    White's moves lose 2, 8, 150, 180, 220 and 180cp (ACPL 123.33) while Black,
    who is winning throughout, loses nothing.

    One ply does not agree exactly, and it is not a frame error: ``move_facts``
    measures the first move against a *level* start ("the initial position,
    level by definition") while the analyzer uses the engine's own evaluation of
    the initial position. Here that is +40 against a +38 position after 1. e4,
    so the analyzer says 2 and ``cp_loss`` says 0 — 0.33cp of ACPL over six
    moves. Every ply from the second on agrees exactly, which is what the
    per-ply assertion below pins.
    """
    engine_answers = [
        _StubEval(evaluation_cp=40.0),      # initial position, White POV
        _StubEval(evaluation_cp=-38.0),     # after 1. e4,    Black POV (White +38)
        _StubEval(evaluation_cp=38.0),      # after 1... e5,  White POV
        _StubEval(evaluation_cp=-30.0),     # after 2. Nf3,   Black POV (White +30)
        _StubEval(evaluation_cp=30.0),      # after 2... Nc6, White POV
        _StubEval(evaluation_cp=120.0),     # after 3. Bb5,   Black POV (White -120)
        _StubEval(evaluation_cp=-120.0),    # after 3... a6,  White POV
        _StubEval(evaluation_cp=300.0),     # after 4. Ba4,   Black POV (White -300)
        _StubEval(evaluation_cp=-300.0),    # after 4... Nf6, White POV
        _StubEval(evaluation_cp=520.0),     # after 5. O-O,   Black POV (White -520)
        _StubEval(evaluation_cp=-520.0),    # after 5... Be7, White POV
        _StubEval(evaluation_cp=700.0),     # after 6. Re1,   Black POV (White -700)
        _StubEval(evaluation_cp=-700.0),    # after 6... b5,  White POV
    ]
    pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5"

    for user_color, expected_acpl in (("white", 740.0 / 6), ("black", 0.0)):
        analyzer = UnifiedChessAnalyzer(engine=_StubEngine(engine_answers))

        result = await analyzer.analyze_game(_pgn(pgn), user_color=user_color, game_id=10)
        assert result is not None

        rows = build_move_facts(
            user_id=1,
            game_id=10,
            user_color=user_color,
            moves=result.all_moves,
        )
        # Same analysis objects in, same plies out.
        assert len(rows) == len(result.all_moves)

        user_rows = [row for row in rows if row["is_user_move"]]
        cp_loss_mean = sum(row["cp_loss"] for row in user_rows) / len(user_rows)
        assert result.user_acpl == pytest.approx(expected_acpl)
        assert result.user_acpl == pytest.approx(cp_loss_mean, abs=1.0)

        # Ply by ply from the second ply on, the two layers are the same number.
        for index, (move, row) in enumerate(zip(result.all_moves, rows)):
            if index == 0:
                continue
            assert move.evaluation_change == pytest.approx(row["cp_loss"], abs=0.05), (
                f"ply {row['ply']} ({row['color']} {row['move_san']}): analyzer says "
                f"{move.evaluation_change}, move_facts says {row['cp_loss']}"
            )
