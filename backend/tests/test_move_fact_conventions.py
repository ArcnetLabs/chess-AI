"""Tests for the per-ply fact conventions the coach's numbers depend on.

These pin the two conventions that a reader (and my own audit script, first time
round) is most likely to misread, and which would silently corrupt every downstream
number if they changed:

* **Perspective alternates by design.** Both stored evaluations are in the *mover's*
  own perspective, so ``eval_before`` of a ply is the *negation* of the previous
  ply's ``eval_after`` — the same position seen by the other player. Comparing them
  without that flip makes the whole library look broken (it made my audit report
  5,830 phantom violations).
* **Loss is clamped at zero.** A move that gained ground records ``cp_loss = 0``, not
  a negative loss, so ``cp_loss`` equals ``max(0, before - after)`` and not the plain
  difference.
"""

from types import SimpleNamespace

from app.services.analysis.move_facts import build_move_facts


def _ply(**overrides) -> SimpleNamespace:
    """One analyzer move entry, with the attributes ``build_move_facts`` reads."""
    base = {
        "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "fen_after": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        "move_uci": "e2e4",
        "move_san": "e4",
        "evaluation_cp": 20.0,
        "best_move_uci": "e2e4",
        "mate_in": None,
        "classification": "good",
    }
    base.update(overrides)
    return SimpleNamespace(**base)

# A short real game line. Evaluations are black-centric centipawns, as stored by the
# analyzer.
PLIES = [
    _ply(),
    _ply(
        fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        fen_after="rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
        move_uci="c7c5",
        move_san="c5",
        evaluation_cp=35.0,
        best_move_uci="c7c5",
    ),
    _ply(
        fen_before="rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
        fen_after="rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        move_uci="g1f3",
        move_san="Nf3",
        evaluation_cp=5.0,
        best_move_uci="g1f3",
    ),
]


def _facts():
    return build_move_facts(
        user_id=1,
        game_id=1,
        user_color="white",
        moves=PLIES,
    )


class TestPerspective:
    def test_eval_before_is_the_previous_ply_from_this_movers_side(self):
        facts = _facts()
        first, second = facts[0], facts[1]

        # Same position, opposite players: the sign flips by design.
        assert second["eval_before_cp"] == -first["eval_after_cp"]

    def test_first_ply_starts_from_level(self):
        facts = _facts()
        assert facts[0]["eval_before_cp"] == 0.0

    def test_evaluations_are_in_the_movers_own_perspective(self):
        """White's advantage is Black's disadvantage, and the mover is recorded."""
        facts = _facts()
        assert facts[0]["color"] == "white"
        assert facts[1]["color"] == "black"
        assert facts[1]["eval_before_cp"] == -facts[0]["eval_after_cp"]


class TestLossClamping:
    def test_cp_loss_is_never_negative(self):
        facts = _facts()
        assert all(fact["cp_loss"] >= 0 for fact in facts)

    def test_cp_loss_matches_the_documented_formula(self):
        facts = _facts()
        for fact in facts:
            expected = max(0.0, fact["eval_before_cp"] - fact["eval_after_cp"])
            assert abs(fact["cp_loss"] - expected) < 0.05, fact

    def test_a_gaining_move_records_zero_not_a_negative_loss(self):
        """A move that improves the position records 0, never a negative loss."""
        facts = _facts()
        for fact in facts:
            raw_difference = fact["eval_before_cp"] - fact["eval_after_cp"]
            if raw_difference < 0:
                assert fact["cp_loss"] == 0.0, fact
