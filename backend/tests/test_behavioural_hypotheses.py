"""Tests for behavioural hypotheses.

The properties that matter, in order of importance:

* it **refuses** to claim a tendency from a thin sample or a trivial gap — the
  failure mode of every "AI coach insight" feature;
* it compares the player against **their own baseline**, not an absolute standard;
* every claim carries the pattern ids that fired in exactly those situations, so it
  can be walked back to occurrences, moves and engine evaluations;
* the wording describes decisions in positions, never the person.
"""

from app.services.patterns.event_pattern_detector import Decision
from app.services.profiles.behavioural_hypotheses import (
    HYPOTHESIS_COMPLEXITY,
    HYPOTHESIS_MATERIAL,
    HYPOTHESIS_PHASE,
    HYPOTHESIS_TRIGGER,
    MIN_HYPOTHESIS_OPPORTUNITIES,
    build_behavioural_hypotheses,
)

TRIGGERED = "middlegame|level|complex|triggered"
SELF_INITIATED = "middlegame|level|complex|self-initiated"
SIMPLIFIED = "endgame|level|simplified|self-initiated"
AHEAD = "middlegame|ahead_slight|complex|self-initiated"


def decision(
    *,
    order: int,
    context: str,
    is_error: bool,
    phase: str = "middlegame",
    pattern_id: int | None = None,
) -> Decision:
    return Decision(
        game_id=order,
        game_order=order,
        context=context,
        phase=phase,
        event_types=("major_blunder",) if is_error else (),
        serious_event_types=("major_blunder",) if is_error else (),
        cp_loss=300.0 if is_error else 0.0,
    )


class _Pattern:
    """Stand-in for a stored pattern."""

    def __init__(self, pattern_id: int, context: str):
        self.id = pattern_id
        self.context_signature = context


def series(*, context: str, errors: int, quiet: int, start: int = 0, phase: str = "middlegame"):
    decisions = []
    for index in range(errors + quiet):
        decisions.append(
            decision(
                order=start + index,
                context=context,
                is_error=index < errors,
                phase=phase,
            )
        )
    return decisions


class TestRefusals:
    """What it must not claim. These are the tests that matter most."""

    def test_no_hypothesis_from_a_thin_sample(self):
        decisions = series(context=TRIGGERED, errors=5, quiet=2) + series(
            context=SELF_INITIATED, errors=1, quiet=30
        )
        assert build_behavioural_hypotheses(decisions) == []

    def test_no_hypothesis_when_the_gap_is_trivial(self):
        # 25 vs 23 opportunities, rates 24% vs 22%: a difference, not a tendency.
        decisions = series(context=TRIGGERED, errors=6, quiet=19) + series(
            context=SELF_INITIATED, errors=5, quiet=18
        )
        assert build_behavioural_hypotheses(decisions) == []

    def test_no_hypothesis_without_a_baseline_rate(self):
        """If nothing ever goes wrong, there is no tendency to describe."""
        decisions = series(context=TRIGGERED, errors=0, quiet=40) + series(
            context=SELF_INITIATED, errors=0, quiet=40
        )
        assert build_behavioural_hypotheses(decisions) == []

    def test_empty_input_is_not_an_error(self):
        assert build_behavioural_hypotheses([]) == []


class TestClaims:
    def test_trigger_sensitivity_is_measured_against_the_own_baseline(self):
        decisions = series(context=TRIGGERED, errors=12, quiet=18) + series(
            context=SELF_INITIATED, errors=4, quiet=36, start=100
        )
        hypotheses = build_behavioural_hypotheses(decisions)
        trigger = [h for h in hypotheses if h["kind"] == HYPOTHESIS_TRIGGER][0]

        assert trigger["group"]["rate"] == 0.4
        assert trigger["baseline"]["rate"] == 0.1
        assert trigger["rate_ratio"] == 4.0
        assert trigger["confidence"] > 0.5

    def test_complexity_tendency(self):
        decisions = series(context=TRIGGERED, errors=14, quiet=16) + series(
            context=SIMPLIFIED, errors=2, quiet=38, start=100, phase="endgame"
        )
        kinds = {h["kind"] for h in build_behavioural_hypotheses(decisions)}
        assert HYPOTHESIS_COMPLEXITY in kinds

    def test_material_tendency(self):
        decisions = series(context=AHEAD, errors=14, quiet=16) + series(
            context=SELF_INITIATED, errors=3, quiet=37, start=100
        )
        kinds = {h["kind"] for h in build_behavioural_hypotheses(decisions)}
        assert HYPOTHESIS_MATERIAL in kinds

    def test_phase_tendency(self):
        decisions = series(context=SIMPLIFIED, errors=16, quiet=24, phase="endgame") + series(
            context=SELF_INITIATED, errors=2, quiet=58, start=100, phase="middlegame"
        )
        phases = build_behavioural_hypotheses(decisions)
        endgame = [h for h in phases if h["kind"] == HYPOTHESIS_PHASE and h["dimension"].get("phase") == "endgame"]
        assert endgame, phases

    def test_sorted_by_confidence(self):
        decisions = (
            series(context=TRIGGERED, errors=18, quiet=2)
            + series(context=SELF_INITIATED, errors=2, quiet=18, start=100)
        )
        confidences = [h["confidence"] for h in build_behavioural_hypotheses(decisions)]
        assert confidences == sorted(confidences, reverse=True)


class TestEvidenceChain:
    def test_only_patterns_from_the_same_situations_are_attached(self):
        decisions = series(context=TRIGGERED, errors=12, quiet=18) + series(
            context=SELF_INITIATED, errors=3, quiet=37, start=100
        )
        here = _Pattern(119, TRIGGERED)
        elsewhere = _Pattern(200, "opening|level|complex|self-initiated")

        trigger = [
            h
            for h in build_behavioural_hypotheses(decisions, [here, elsewhere])
            if h["kind"] == HYPOTHESIS_TRIGGER
        ][0]

        assert trigger["pattern_ids"] == [119]
        assert 200 not in trigger["pattern_ids"]

    def test_thresholds_travel_with_the_claim(self):
        """A claim must be re-derivable, so its gates are stored beside it."""
        decisions = series(context=TRIGGERED, errors=12, quiet=18) + series(
            context=SELF_INITIATED, errors=3, quiet=37, start=100
        )
        hypothesis = build_behavioural_hypotheses(decisions)[0]

        assert hypothesis["thresholds"]["min_opportunities"] == MIN_HYPOTHESIS_OPPORTUNITIES
        assert "min_rate_ratio" in hypothesis["thresholds"]
        assert "min_rate_gap" in hypothesis["thresholds"]


class TestWording:
    def test_statements_describe_decisions_not_the_person(self):
        decisions = series(context=TRIGGERED, errors=12, quiet=18) + series(
            context=SELF_INITIATED, errors=3, quiet=37, start=100
        )
        for hypothesis in build_behavioural_hypotheses(decisions):
            statement = hypothesis["statement"].lower()
            # No personality diagnosis (the ban is on trait claims, not on the words
            # "you are", which appear in legitimate phrasing like "when you are left
            # to your own plans"), and no engine vocabulary.
            for banned in (
                "impatient",
                "careless",
                "reckless",
                "lazy",
                "you are a ",
                "your personality",
                "your character",
                "acpl",
                "centipawn",
                "blunder rate",
            ):
                assert banned not in statement, statement
            # It does state the comparison it is making.
            assert "%" in statement

    def test_statement_names_both_rates(self):
        decisions = series(context=TRIGGERED, errors=12, quiet=18) + series(
            context=SELF_INITIATED, errors=4, quiet=36, start=100
        )
        trigger = [
            h for h in build_behavioural_hypotheses(decisions) if h["kind"] == HYPOTHESIS_TRIGGER
        ][0]
        assert "40%" in trigger["statement"]
        assert "10%" in trigger["statement"]
