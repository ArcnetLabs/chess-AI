"""What a pattern card says, and the numbers it is allowed to say it with.

Two shipped defects, one shape: a card's copy disagreed with the data behind it.

**The body counted the wrong games.** A phase card's badge is built from
``affected_games_count`` — the games the pattern actually covers — and the body
counted something else. The opening card read "26 games" above "problems in the
first phase of 50 games", because the sentence used ``games_count``: every game
that had a figure for that phase, whether or not it cleared the threshold. The
two only differ when some games are fine, which is the normal case, and on a real
account the gap was 26 against 50. The badge is the specific, defensible claim, so
the body states the same number, and the audit below covers every detector in the
package that puts a game count in a sentence.

**The claims were verdicts, and two verdicts about one phase cannot both be
true.** "Your openings are where you give ground" and "Strength: your opening play
holds up" are opposites, and one real profile carried both at once. As
*measurements* they never conflicted: the first is a magnitude (the phase's average
loss per move against a threshold), the second a rate (significant errors per
opportunity), and a player can genuinely be rare to err and expensive when they do
— 9 errors in 368 decisions, at 46.6 centipawns per move against a 30.0 bar. Only
the wording made them mutually exclusive, so the wording is what is scoped here:

* a **rate** claim says how *often* something goes wrong ("you rarely go badly
  wrong in the opening"), and carries the decisions it was measured over;
* a **magnitude** claim says what it *cost*, over the games it happened in ("cost
  you dearly in 26 games");
* a **relative** claim, used by the profile summary, compares the phases with each
  other and is worded as a comparison.

Each claim sits on one axis, so none can deny another. Nothing here hard-codes a
count: re-detection on corrected data moves these numbers (one phase went from 50
occurrences to 25), so every expected number is derived from its fixture, and the
fixtures assert that they can tell the two counts apart.
"""

import re
from typing import Optional

import pytest

from app.services.patterns.blunder_cluster_detector import detect_blunder_clusters
from app.services.patterns.constants import (
    ENDGAME_ACPL_THRESHOLD,
    MIDDLEGAME_ACPL_THRESHOLD,
    OPENING_ACPL_THRESHOLD,
    OPENING_SPECIFIC_ACPL_THRESHOLD,
)
from app.services.patterns.event_pattern_detector import Decision, detect_strengths
from app.services.patterns.opening_weakness_detector import detect_opening_weaknesses
from app.services.patterns.phase_weakness_detector import detect_phase_weaknesses
from app.services.patterns.types import PatternAggregationInput
from app.services.profiles.profile_builder import (
    PHASE_STRENGTH_SCORE,
    _build_phase_performance,
    _compose_profile_summary,
    _derive_archetype,
    _derive_strengths_weaknesses,
)

# An unscoped verdict: a judgement word tied to a phase, or the phase named as the
# place ground is given. That is the shape the shipped copy had, and the shape two
# surfaces can disagree about. Scoped claims — a rate, a magnitude over N games, a
# comparison — are deliberately not matched, so the check is about the shape of the
# claim rather than about any particular phrasing.
_UNSCOPED_VERDICT = re.compile(
    r"\b(strong|strongest|weak|weakest|solid|poor|reliable|leak|best|worst)\b"
    r"[^.]{0,40}?\b(opening|openings|middlegame|endgame|endgames)\b"
    r"|\b(opening|openings|middlegame|endgame|endgames)\b[^.]{0,40}?\bgive ground\b",
    re.IGNORECASE,
)

_RATE_ANCHORS = ("rarely", "seldom", "hardly ever", "not often")
_MAGNITUDE_ANCHORS = ("cost you", "costs you", "expensive")

# The wording that shipped the contradiction, kept as a regression pin so a revert
# to any of it fails here rather than on a player's profile page.
_SHIPPED_VERDICTS = (
    "Strongest area",
    "Strong opening",
    "Strong endgame",
    "give ground",
    "holds up",
)


def unscoped_verdict(text: str) -> Optional[str]:
    """The unscoped phase verdict ``text`` contains, if any."""
    match = _UNSCOPED_VERDICT.search(text)
    return match.group(0) if match else None


def phase_aggregation(
    *,
    phase: str,
    threshold: float,
    high: float,
    low: float,
    over_threshold: int,
    under_threshold: int,
) -> tuple[PatternAggregationInput, int, int]:
    """Aggregation where only some games clear ``phase``'s threshold.

    Returns the input plus ``(affected, analysed)`` — the games the pattern covers
    and the games that had a figure for the phase at all. Callers assert the two
    differ, so a fixture that stops exercising the distinction fails loudly instead
    of passing vacuously.
    """
    values = [high] * over_threshold + [low] * under_threshold
    assert sum(values) / len(values) > threshold, "fixture no longer fires the pattern"
    affected = sum(1 for value in values if value > threshold)
    assert affected < len(values), "fixture cannot tell the two counts apart"

    rows = [
        {
            "game_id": index + 1,
            f"{phase}_acpl": value,
            "opening_name": "Sicilian Defense",
        }
        for index, value in enumerate(values)
    ]
    aggregation = PatternAggregationInput(
        user_id=1,
        total_analyzed_games=len(values),
        opening_acpls=values if phase == "opening" else [],
        middlegame_acpls=values if phase == "middlegame" else [],
        endgame_acpls=values if phase == "endgame" else [],
        opening_by_game=rows,
    )
    return aggregation, affected, len(values)


# One case per phase: the three descriptions are three separate sentences, so each
# is checked on its own rather than through a single representative.
PHASE_CASES = [
    ("opening", OPENING_ACPL_THRESHOLD, 60.0, 5.0, 26, 24),
    ("middlegame", MIDDLEGAME_ACPL_THRESHOLD, 70.0, 5.0, 15, 10),
    ("endgame", ENDGAME_ACPL_THRESHOLD, 80.0, 5.0, 12, 8),
]


def opening_strength_decisions() -> list[Decision]:
    """The shape ``detect_strengths`` needs: many quiet decisions, one real error."""
    decisions = [
        Decision(
            game_id=index,
            game_order=index,
            cp_loss=5.0,
            phase="opening",
            context="opening|level|quiet",
        )
        for index in range(30)
    ]
    decisions.append(
        Decision(
            game_id=99,
            game_order=99,
            event_types=("opening_deviation",),
            serious_event_types=("opening_deviation",),
            cp_loss=200.0,
            phase="opening",
            context="opening|level|quiet",
        )
    )
    return decisions


class TestTheBodyCountsTheGamesThePatternCovers:
    """Every game count in a body sentence equals ``affected_games_count``."""

    @pytest.mark.parametrize("phase,threshold,high,low,over,under", PHASE_CASES)
    def test_a_phase_card_states_the_affected_games(
        self, phase, threshold, high, low, over, under
    ):
        aggregation, affected, analysed = phase_aggregation(
            phase=phase,
            threshold=threshold,
            high=high,
            low=low,
            over_threshold=over,
            under_threshold=under,
        )

        patterns = [
            pattern
            for pattern in detect_phase_weaknesses(aggregation)
            if pattern.pattern_subtype == f"high_{phase}_acpl"
        ]
        assert len(patterns) == 1
        pattern = patterns[0]

        assert affected < analysed, "fixture cannot tell the two counts apart"
        assert pattern.affected_games_count == affected
        assert f"{affected} games" in pattern.pattern_description
        # The number the body used to print: every game that had a figure for this
        # phase, most of which were not the problem.
        assert f"{analysed} games" not in pattern.pattern_description

    def test_a_phase_strength_states_the_affected_games(self):
        pattern = detect_strengths(opening_strength_decisions())[0]

        assert f"{pattern.affected_games_count} games" in pattern.pattern_description

    def test_an_opening_leak_states_the_games_over_the_bar(self):
        # Three of the five games in this line went over the bar, and the average
        # across the line is over the threshold, so the pattern fires on the line.
        values = [80.0, 80.0, 80.0, 20.0, 20.0]
        analysed = len(values)
        affected = sum(1 for value in values if value > OPENING_SPECIFIC_ACPL_THRESHOLD)
        assert sum(values) / analysed > OPENING_SPECIFIC_ACPL_THRESHOLD
        assert affected < analysed

        aggregation = PatternAggregationInput(
            user_id=1,
            total_analyzed_games=analysed,
            opening_acpls=values,
            middlegame_acpls=[],
            endgame_acpls=[],
            opening_by_game=[
                {
                    "game_id": index + 1,
                    "opening_name": "Sicilian Defense",
                    "opening_eco": "B90",
                    "opening_acpl": value,
                }
                for index, value in enumerate(values)
            ],
        )

        pattern = detect_opening_weaknesses(aggregation)[0]

        assert pattern.affected_games_count == affected
        assert f"{affected} of these games" in pattern.pattern_description
        assert f"{analysed} of these games" not in pattern.pattern_description

    def test_the_legacy_blunder_cluster_states_the_games_with_a_blunder(self):
        counts = [3, 3, 3, 0, 0, 0]
        analysed = len(counts)
        affected = sum(1 for count in counts if count >= 1)
        assert affected < analysed

        aggregation = PatternAggregationInput(
            user_id=1,
            total_analyzed_games=analysed,
            opening_acpls=[],
            middlegame_acpls=[],
            endgame_acpls=[],
            opening_by_game=[],
            # No move-level events, which is what routes this to the legacy aggregate.
            blunder_events=[],
            games_blunder_stats=[
                {"game_id": index + 1, "blunder_count": count}
                for index, count in enumerate(counts)
            ],
        )

        pattern = detect_blunder_clusters(aggregation)[0]

        assert pattern.affected_games_count == affected
        assert f"{affected} games" in pattern.pattern_description
        assert f"{analysed} games" not in pattern.pattern_description


class TestEveryPhaseClaimSitsOnOneAxis:
    """A phase claim is a rate, a magnitude or a comparison — never a verdict."""

    @pytest.mark.parametrize("phase,threshold,high,low,over,under", PHASE_CASES)
    def test_the_phase_leak_is_a_magnitude(self, phase, threshold, high, low, over, under):
        aggregation, _, _ = phase_aggregation(
            phase=phase,
            threshold=threshold,
            high=high,
            low=low,
            over_threshold=over,
            under_threshold=under,
        )
        pattern = [
            candidate
            for candidate in detect_phase_weaknesses(aggregation)
            if candidate.pattern_subtype == f"high_{phase}_acpl"
        ][0]

        description = pattern.pattern_description
        assert any(anchor in description.lower() for anchor in _MAGNITUDE_ANCHORS)
        assert unscoped_verdict(description) is None

    def test_the_phase_strength_is_a_rate(self):
        pattern = detect_strengths(opening_strength_decisions())[0]

        description = pattern.pattern_description
        assert any(anchor in description.lower() for anchor in _RATE_ANCHORS)
        assert unscoped_verdict(description) is None
        # A rate without its denominator is a bare count.
        assert f"{pattern.opportunity_count} decisions" in description

    def test_one_phase_can_be_both_and_each_claim_keeps_out_of_the_other(self):
        """The diagnosed case: rare errors in the opening, each one expensive.

        ``solid_opening`` counts significant errors per decision and
        ``high_opening_acpl`` measures the phase's average loss per move, so both
        are true of one opening. Neither sentence may claim the phase outright, or
        the profile contradicts itself on the page.
        """
        aggregation, _, _ = phase_aggregation(
            phase="opening",
            threshold=OPENING_ACPL_THRESHOLD,
            high=60.0,
            low=5.0,
            over_threshold=26,
            under_threshold=24,
        )
        weakness = [
            candidate
            for candidate in detect_phase_weaknesses(aggregation)
            if candidate.pattern_subtype == "high_opening_acpl"
        ][0]
        strength = detect_strengths(opening_strength_decisions())[0]

        assert strength.pattern_subtype == "solid_opening"
        assert "opening" in weakness.pattern_description.lower()
        assert "opening" in strength.pattern_description.lower()

        # Different axes, which is exactly why both can be true at once.
        assert any(
            anchor in strength.pattern_description.lower() for anchor in _RATE_ANCHORS
        )
        assert any(
            anchor in weakness.pattern_description.lower()
            for anchor in _MAGNITUDE_ANCHORS
        )

        for description in (weakness.pattern_description, strength.pattern_description):
            assert unscoped_verdict(description) is None


def three_phase_aggregation() -> tuple[PatternAggregationInput, int]:
    """A corpus shaped like the account the contradiction was found on.

    The opening clears the phase weakness threshold — so the leak fires — and is
    *still* the player's least costly phase by average loss per move, which is the
    combination that produced two opposite verdicts about one opening. The
    middlegame sits between the two so there is something to rank on both sides.

    Returns the input and the number of games the opening leak covers.
    """
    opening_values = [60.0] * 26 + [5.0] * 24
    middlegame_values = [60.0] * 20
    endgame_values = [110.0] * 20
    assert sum(opening_values) / len(opening_values) > OPENING_ACPL_THRESHOLD
    opening_affected = sum(
        1 for value in opening_values if value > OPENING_ACPL_THRESHOLD
    )
    assert opening_affected < len(opening_values), "fixture cannot tell the counts apart"

    rows = []
    for index, opening_acpl in enumerate(opening_values):
        row = {
            "game_id": index + 1,
            "opening_acpl": opening_acpl,
            "opening_name": "Sicilian Defense",
        }
        if index < len(middlegame_values):
            row["middlegame_acpl"] = middlegame_values[index]
            row["endgame_acpl"] = endgame_values[index]
        rows.append(row)

    aggregation = PatternAggregationInput(
        user_id=1,
        total_analyzed_games=len(opening_values),
        opening_acpls=opening_values,
        middlegame_acpls=middlegame_values,
        endgame_acpls=endgame_values,
        opening_by_game=rows,
    )
    return aggregation, opening_affected


class TestTheComposedSummaryNeverPrintsOppositeVerdicts:
    """The profile summary, on a player whose opening is both a strength and a leak.

    Diagnosed on a real account: the patterns page read "Your openings are where you
    give ground", while the profile summary read "Strongest area: your opening play"
    and carried "Strong opening performance (82/100)" among the strengths. Both were
    true, because the two rows measure different things — significant errors per
    opportunity (a rate: 9 in 368 decisions) against the phase's average loss per move
    (a magnitude: 46.6 against a 30.0 bar).

    The fix is in the copy, so this is what is pinned: with both on one profile, the
    composed summary and the strength/weakness lists it is composed from must not put
    two mutually exclusive claims about one phase on the page. No count is asserted
    here — re-detection moves them.
    """

    def test_a_phase_that_is_both_least_costly_and_expensive(self):
        aggregation, opening_affected = three_phase_aggregation()
        leaks = detect_phase_weaknesses(aggregation)
        opening_leak = [
            pattern
            for pattern in leaks
            if pattern.pattern_subtype == "high_opening_acpl"
        ][0]
        opening_strength = detect_strengths(opening_strength_decisions())[0]

        phase_performance = _build_phase_performance(aggregation)
        archetype = _derive_archetype(phase_performance)
        strengths, weaknesses = _derive_strengths_weaknesses(
            [opening_strength, *leaks], phase_performance
        )
        summary = _compose_profile_summary(
            archetype=archetype,
            games_analyzed_count=aggregation.total_analyzed_games,
            patterns_detected_count=len(leaks) + 1,
            primary_strengths=strengths,
            primary_weaknesses=weaknesses,
            style_indicators={},
            tactical_themes={},
            phase_performance=phase_performance,
        )

        # The player is genuinely in both states at once, or this proves nothing: the
        # opening is the best phase on the 0-100 scale *and* the leak covers only some
        # of the games analysed.
        assert phase_performance["opening"] >= PHASE_STRENGTH_SCORE
        assert opening_affected < aggregation.total_analyzed_games
        assert opening_leak.affected_games_count == opening_affected

        composed = " ".join([summary, *strengths, *weaknesses])
        assert "opening" in composed.lower()

        # Both claims survive on their own axis: a rate for the strength, a magnitude
        # for the leak. Scoping each one is what makes them compatible.
        assert any(
            anchor in opening_strength.pattern_description.lower()
            for anchor in _RATE_ANCHORS
        )
        assert any(
            anchor in opening_leak.pattern_description.lower()
            for anchor in _MAGNITUDE_ANCHORS
        )

        # And nothing on the page states a verdict the other denies.
        for text in (summary, archetype, *strengths, *weaknesses):
            assert unscoped_verdict(text) is None, text
        for shipped in _SHIPPED_VERDICTS:
            assert shipped not in composed

    def test_the_phase_ranking_is_stated_as_a_comparison(self):
        """The three phases are ranked, so the honest claim is the comparison."""
        aggregation, _ = three_phase_aggregation()
        phase_performance = _build_phase_performance(aggregation)

        summary = _compose_profile_summary(
            archetype=_derive_archetype(phase_performance),
            games_analyzed_count=aggregation.total_analyzed_games,
            patterns_detected_count=0,
            primary_strengths=[],
            primary_weaknesses=[],
            style_indicators={},
            tactical_themes={},
            phase_performance=phase_performance,
        )

        assert "Compared with your other phases" in summary
        assert unscoped_verdict(summary) is None

