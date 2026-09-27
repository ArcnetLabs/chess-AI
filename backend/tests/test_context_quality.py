"""Tests for the context-quality verifier.

The verifier is the gate that says whether coaching context is fit to coach from,
so it is only useful if it actually fails on bad context. These tests feed it the
exact defect found in production — a context block missing the grounding rule —
and require a failure, plus the cases it must not flag.

Why this file exists at all: the production run of this check found the no-history
prompt had no grounding rule while the two history prompts did. A checker that
only ever returns "pass" would have hidden that, so the fail-path is asserted.
"""

from app.services.chat.event_context import GROUNDING_RULE, absence_context
from app.services.evaluation.context_quality import (
    summarise_context_checks,
    verify_context_quality,
)

GOOD_HISTORY = (
    f"{GROUNDING_RULE}\n\n"
    "## Your recurring pattern\n"
    "In the endgame you give back a piece after the opponent attacks. "
    "pattern_id=119, 29 times across 18 games."
)


class TestGroundingRule:
    def test_history_context_without_the_rule_fails(self):
        """The real defect: evidence with nothing forbidding invention."""
        checks = verify_context_quality(
            "## Your recurring pattern\npattern_id=119, 29 times.",
            name="history",
            expect_history=True,
        )
        assert not checks.passed
        assert checks.checks["grounding_rule_present"] is False
        assert any("invent" in v for v in checks.violations)

    def test_real_absence_context_passes(self):
        checks = verify_context_quality(
            absence_context(), name="no_history", expect_history=False
        )
        assert checks.passed, checks.violations

    def test_history_context_with_the_rule_passes(self):
        checks = verify_context_quality(
            GOOD_HISTORY, name="history", expect_history=True
        )
        assert checks.passed, checks.violations


class TestEvidenceRules:
    def test_history_without_a_citable_id_fails(self):
        """A claim the player cannot trace back is not admissible evidence."""
        checks = verify_context_quality(
            f"{GROUNDING_RULE}\n\nYou keep losing endgames.",
            name="history",
            expect_history=True,
        )
        assert not checks.passed
        assert checks.checks["citable_evidence"] is False

    def test_absence_must_be_stated_when_there_is_no_history(self):
        checks = verify_context_quality(
            f"{GROUNDING_RULE}\n\n## Player history\n(empty)\n",
            name="no_history",
            expect_history=False,
        )
        assert not checks.passed
        assert checks.checks["absence_stated"] is False

    def test_game_reference_counts_as_citable(self):
        checks = verify_context_quality(
            f"{GROUNDING_RULE}\n\nThis resembles game 42, where the same thing happened.",
            name="history",
            expect_history=True,
        )
        assert checks.checks["citable_evidence"] is True


class TestJargon:
    def test_engine_vocabulary_is_flagged(self):
        checks = verify_context_quality(
            f"{GROUNDING_RULE}\n\nYour ACPL is high; centipawn loss above threshold.",
            name="history",
            expect_history=True,
        )
        assert not checks.passed
        assert checks.checks["no_engine_jargon"] is False
        assert "acpl" in " ".join(checks.violations)

    def test_player_facing_wording_is_not_flagged(self):
        checks = verify_context_quality(
            GOOD_HISTORY, name="history", expect_history=True
        )
        assert checks.checks["no_engine_jargon"] is True


class TestSummary:
    def test_summary_counts_contexts_and_checks(self):
        passing = verify_context_quality(
            GOOD_HISTORY, name="history", expect_history=True
        )
        failing = verify_context_quality(
            "## Pattern\npattern_id=1", name="bad", expect_history=True
        )
        summary = summarise_context_checks([passing, failing])

        assert summary["contexts"] == 2
        assert summary["contexts_passed"] == 1
        assert summary["checks_total"] == len(passing.checks) + len(failing.checks)
        assert summary["checks_passed"] < summary["checks_total"]
        assert summary["violations"]

    def test_empty_result_is_not_reported_as_passing(self):
        """No checks run must never read as success."""
        from app.services.evaluation.context_quality import ContextChecks

        assert ContextChecks(name="empty").passed is False
