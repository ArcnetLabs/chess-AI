"""Model-side evaluation tests.

The scorer is the gate that will decide whether fine-tuning is justified, so it
is tested against planted replies: one that respects the evidence and one that
breaks each rule in turn. A scorer that cannot fail proves nothing.
"""

import pytest

from app.services.evaluation.model_eval import (
    BANNED_COACH_TERMS,
    Probe,
    run_probes,
    score_reply,
)

HISTORY_CONTEXT = (
    "## Recurring patterns in this kind of position\n"
    "- recurring issue: an endgame technique error (37% of 79 similar decisions; pattern_id=119)\n"
    "## Similar positions from your own games\n"
    "- Game 36 move 50: you played d3e4, better was c7d6, the game ended white\n"
)
ABSENCE_CONTEXT = (
    "## Player history for this position\n"
    "Nothing on record for this kind of position yet. Say plainly that this is new."
)


def history_probe() -> Probe:
    return Probe(
        name="with_history",
        question="What should I be thinking about here?",
        context=HISTORY_CONTEXT,
        expects_history=True,
        allowed_game_ids=[36],
        allowed_pattern_ids=[119],
    )


def absence_probe() -> Probe:
    return Probe(
        name="no_history",
        question="Have I had trouble like this before?",
        context=ABSENCE_CONTEXT,
        expects_history=False,
        expects_uncertainty=True,
    )


class TestGoodReplies:
    def test_a_grounded_personal_reply_passes(self):
        reply = (
            "This is the kind of endgame where you have slipped before — in Game 36 you "
            "played d3e4 when c7d6 kept the rook active. The same idea applies here: "
            "improve the rook first, then push."
        )
        result = score_reply(history_probe(), reply)
        assert result.passed, result.violations

    def test_an_honest_absence_reply_passes(self):
        reply = (
            "I don't have anything on record for this kind of position, so this is new "
            "for you. From the position itself, the priority is king activity."
        )
        result = score_reply(absence_probe(), reply)
        assert result.passed, result.violations


class TestPlantedViolations:
    def test_catches_a_game_id_not_in_the_evidence(self):
        reply = "In Game 999 you played d3e4, which lost the thread."
        result = score_reply(history_probe(), reply)
        assert not result.passed
        assert any("999" in v for v in result.violations)

    def test_catches_a_pattern_id_not_in_the_evidence(self):
        reply = "This is your endgame problem again (pattern_id=777)."
        result = score_reply(history_probe(), reply)
        assert not result.passed
        assert any("777" in v for v in result.violations)

    def test_catches_an_invented_evaluation(self):
        reply = "The engine says +2.35 for you here, so push the pawn."
        result = score_reply(history_probe(), reply)
        assert not result.passed
        assert any("2.35" in v for v in result.violations)

    def test_catches_engine_jargon(self):
        reply = "Your ACPL in these positions is worse than your threshold suggests. In Game 36 you played d3e4."
        result = score_reply(history_probe(), reply)
        assert not result.passed
        assert any("engine vocabulary" in v for v in result.violations)

    def test_catches_ignoring_the_supplied_history(self):
        reply = "Generally, in such endgames you should activate your king and create a passed pawn."
        result = score_reply(history_probe(), reply)
        assert not result.passed
        assert any("ignores it" in v for v in result.violations)

    def test_catches_a_pattern_claim_with_no_history(self):
        reply = "Yes — this is a recurring pattern of yours, you always get impatient here."
        result = score_reply(absence_probe(), reply)
        assert not result.passed
        assert any("claimed a pattern" in v for v in result.violations)

    def test_catches_silence_about_missing_history(self):
        reply = "Activate your king and push the outside pawn."
        result = score_reply(absence_probe(), reply)
        assert not result.passed
        assert any("did not say so" in v for v in result.violations)


class TestHarnessBehaviour:
    def test_without_a_provider_the_prompts_are_still_reported(self):
        report = run_probes(None, [history_probe(), absence_probe()], provider=None)
        assert report["provider"] == "unavailable"
        assert report["scored"] == 0
        # The unmeasured gap must be visible, with the exact context assembled.
        assert len(report["prompts"]) == 2
        assert "pattern_id=119" in report["prompts"][0]["context_preview"]

    def test_with_a_stub_provider_replies_are_scored(self):
        def stub(system_prompt: str, user_prompt: str) -> str:
            return f"Responding with the evidence given. {user_prompt[:0]}"

        report = run_probes(None, [history_probe()], provider=stub)
        assert report["provider"] == "configured"
        assert report["scored"] == 1
        # The stub ignores the history, which the scorer must catch.
        assert report["passed"] == 0

    def test_a_provider_fault_is_reported_not_raised(self):
        def broken(system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("upstream 503")

        report = run_probes(None, [history_probe()], provider=broken)
        assert report["scored"] == 0
        assert "503" in report["results"][0]["skipped"]

    def test_banned_terms_are_the_product_rule(self):
        assert "acpl" in BANNED_COACH_TERMS
        assert "centipawn" in BANNED_COACH_TERMS
