"""Regression gate for the coaching evaluation harness.

The harness itself lives in ``app/services/evaluation/coach_eval.py`` and runs
offline (no engine, no model). These tests make it part of the normal suite, so a
change that breaks pattern recognition, grounding or personalisation fails here
rather than being discovered in production.

Floors are the measured baseline, deliberately not aspirational: they catch
regressions, and raising them is a deliberate act when the system improves.
"""

import pytest

from app.services.evaluation.coach_eval import (
    build_cases,
    run_harness,
    verify_grounding,
    verify_no_invented_evaluations,
    verify_personalisation,
)

# Measured baseline (see the phase 7 delivery notes).
MIN_CASES_PASSED = 6
MIN_PATTERN_RECALL = 0.85
MIN_PATTERN_PRECISION = 0.99
MAX_FALSE_PATTERN_RATE = 0.05


_REPORT: dict = {}


@pytest.fixture
def report(db):
    """Run the harness once against the suite's SQLite fixture, then reuse it.

    Uses the standard ``db`` fixture rather than building an engine here: an
    earlier version imported ``app.core.database.engine`` directly and tried to
    reach the production Postgres from a unit test.
    """
    if "value" not in _REPORT:
        _REPORT["value"] = run_harness(db)
    return _REPORT["value"]


class TestHarnessScores:
    def test_cases_pass_at_or_above_baseline(self, report):
        failures = [c["name"] for c in report["case_results"] if not c["passed"]]
        assert report["cases_passed"] >= MIN_CASES_PASSED, f"failing cases: {failures}"

    def test_pattern_recall(self, report):
        assert report["pattern_recall"] >= MIN_PATTERN_RECALL

    def test_pattern_precision(self, report):
        assert report["pattern_precision"] >= MIN_PATTERN_PRECISION

    def test_false_pattern_rate_is_bounded(self, report):
        """Inventing a pattern is worse than missing one: it becomes coaching."""
        assert report["false_pattern_rate"] <= MAX_FALSE_PATTERN_RATE

    def test_no_grounding_violations(self, report):
        assert report["grounding_violations"] == 0

    def test_covers_the_difficult_categories(self, report):
        categories = {c["category"] for c in report["case_results"]}
        assert {
            "pattern_identification",
            "pattern_vs_isolated_error",
            "opponent_pattern",
            "opening_recommendation",
            "uncertainty",
            "grounding",
        } <= categories


class TestVerifiers:
    """The gate itself must detect planted faults, or it proves nothing."""

    def test_catches_a_cited_game_not_in_evidence(self):
        violations = verify_grounding(
            "## Similar positions\n- Game 999 move 10: you played e4",
            allowed_game_ids=[1, 2, 3],
            allowed_pattern_ids=[],
        )
        assert violations and "999" in violations[0]

    def test_accepts_a_cited_game_that_is_in_evidence(self):
        assert verify_grounding(
            "## Similar positions\n- Game 2 move 10", allowed_game_ids=[1, 2], allowed_pattern_ids=[]
        ) == []

    def test_catches_a_pattern_id_not_in_evidence(self):
        violations = verify_grounding(
            "- recurring issue (pattern_id=42)", allowed_game_ids=[], allowed_pattern_ids=[7]
        )
        assert violations and "42" in violations[0]

    def test_catches_an_invented_evaluation(self):
        violations = verify_no_invented_evaluations(
            "The engine said +1.75 here.", context="Evaluation: -0.40"
        )
        assert violations and "1.75" in violations[0]

    def test_accepts_an_evaluation_taken_from_the_context(self):
        assert verify_no_invented_evaluations(
            "The engine said -0.40 here.", context="Evaluation: -0.40"
        ) == []

    def test_personalisation_requires_a_real_difference(self):
        assert verify_personalisation("history A", "history B") is True
        assert verify_personalisation("same", "same") is False


class TestCases:
    def test_case_names_are_unique(self):
        names = [case.name for case in build_cases()]
        assert len(names) == len(set(names))

    def test_every_case_expects_something(self):
        """A case that asserts nothing would pad the pass count."""
        for case in build_cases():
            asserts_something = bool(
                case.expected_event_types
                or case.forbidden_event_types
                or case.expected_strength
                or case.expected_signatures
                or case.expect_no_patterns
            )
            assert asserts_something, f"{case.name} asserts nothing"
