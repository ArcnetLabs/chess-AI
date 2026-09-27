"""Tests for context-aware, event-driven pattern detection.

The properties that matter, and are asserted here:

* a pattern is a *rate* over opportunities, never a bare count;
* grouping is by situation, so unrelated mistakes of one label stay separate;
* small samples never become patterns, however striking;
* trend comes from the decision series by game recency, and can say
  "improving" or "resolved" as well as "persistent";
* strengths are detected by the same standard;
* everything a claim rests on is inside the evidence payload.
"""

from app.services.patterns.context_signature import (
    context_signature,
    describe_context,
    material_state,
)
from app.services.patterns.event_pattern_detector import (
    MIN_DISTINCT_GAMES,
    MIN_OCCURRENCES,
    MIN_OPPORTUNITIES,
    Decision,
    detect_context_patterns,
    detect_strengths,
)

LOW_POSITION_FEATURES = {
    "material_balance": 0,
    "material_band": "level",
    "simplified": False,
}


def decision(
    *,
    game_id: int,
    game_order: int,
    context: str,
    phase: str = "middlegame",
    event_types=(),
    serious_event_types=None,
    cp_loss: float = 0.0,
) -> Decision:
    """Build a decision. By default its events count as serious (high severity).

    Strength detection deliberately looks at serious events only, so tests that
    care about that distinction pass ``serious_event_types`` explicitly.
    """
    types = tuple(event_types)
    serious = types if serious_event_types is None else tuple(serious_event_types)
    return Decision(
        game_id=game_id,
        game_order=game_order,
        event_types=types,
        serious_event_types=serious,
        cp_loss=cp_loss,
        phase=phase,
        context=context,
    )


class TestContextSignature:
    def test_material_state_keeps_direction(self):
        assert material_state({"material_band": "level"}) == "level"
        assert (
            material_state({"material_band": "clear", "material_balance": 500})
            == "ahead_clear"
        )
        assert (
            material_state({"material_band": "clear", "material_balance": -500})
            == "behind_clear"
        )

    def test_signature_separates_situations(self):
        complex_pos = context_signature(
            phase="middlegame",
            features={"material_band": "level", "simplified": False},
            structure_key="abc123",
            has_opponent_trigger=False,
        )
        endgame_pos = context_signature(
            phase="endgame",
            features={"material_band": "level", "simplified": True},
            structure_key="abc123",
            has_opponent_trigger=True,
        )
        assert complex_pos != endgame_pos

    def test_signature_is_stable_for_the_same_situation(self):
        args = dict(
            phase="endgame",
            features={"material_band": "slight", "material_balance": 200, "simplified": True},
            structure_key="deadbeef",
            has_opponent_trigger=True,
        )
        assert context_signature(**args) == context_signature(**args)

    def test_description_avoids_engine_vocabulary(self):
        signature = context_signature(
            phase="endgame",
            features={"material_band": "level", "simplified": True},
            structure_key="abc",
            has_opponent_trigger=True,
        )
        text = describe_context(signature)
        for banned in ("acpl", "centipawn", "eval", "cp ", "signature"):
            assert banned not in text.lower()


class TestContextPatternDetection:
    def _series(
        self,
        *,
        error_orders: set[int],
        total_games: int = 20,
        context: str = "middlegame|level|complex|abc|self-initiated",
        event_type: str = "major_blunder",
    ):
        """Decision series where `game_order` is recency (0 = most recent game).

        Errors are placed at explicit orders so a test states the timeline it
        means instead of relying on insertion order.
        """
        return [
            decision(
                game_id=order,
                game_order=order,
                context=context,
                event_types=(event_type,) if order in error_orders else (),
                cp_loss=400.0 if order in error_orders else 10.0,
            )
            for order in range(total_games)
        ]

    def test_pattern_requires_repetition_across_games(self):
        decisions = self._series(error_orders={0, 1, 2, 3, 4})
        patterns = detect_context_patterns(decisions)
        assert len(patterns) == 1
        assert patterns[0].occurrence_count == 5
        assert patterns[0].affected_games_count == 5

    def test_two_errors_are_not_a_pattern(self):
        decisions = self._series(error_orders={0, 1})
        assert detect_context_patterns(decisions) == []

    def test_thin_context_is_rejected_however_striking(self):
        """3 errors out of 3 decisions is not evidence."""
        context = "endgame|level|simplified|xyz|triggered"
        decisions = [
            decision(
                game_id=i,
                game_order=i,
                context=context,
                phase="endgame",
                event_types=("endgame_technique_failure",),
                cp_loss=300.0,
            )
            for i in range(MIN_OCCURRENCES)
        ]
        assert len(decisions) < MIN_OPPORTUNITIES  # guard the premise of the test
        assert detect_context_patterns(decisions) == []

    def test_rate_uses_opportunities_not_counts(self):
        decisions = self._series(error_orders={0, 1, 2})
        pattern = detect_context_patterns(decisions)[0]
        assert pattern.opportunity_count == 20
        assert pattern.occurrence_rate == round(3 / 20, 4)
        assert "15%" in pattern.pattern_description

    def test_unrelated_contexts_do_not_merge(self):
        """Same label, different situations — two separate patterns."""
        decisions = []
        for i in range(4):
            decisions.append(
                decision(
                    game_id=i,
                    game_order=i,
                    context="opening|level|complex|aaa|self-initiated",
                    phase="opening",
                    event_types=("opening_deviation",),
                    cp_loss=200.0,
                )
            )
        for i in range(4, 8):
            decisions.append(
                decision(
                    game_id=i,
                    game_order=i,
                    context="endgame|behind_slight|simplified|bbb|triggered",
                    phase="endgame",
                    event_types=("opening_deviation",),
                    cp_loss=200.0,
                )
            )
        # Filler decisions so both contexts clear the opportunity floor.
        for i in range(8, 40):
            ctx = (
                "opening|level|complex|aaa|self-initiated"
                if i % 2 == 0
                else "endgame|behind_slight|simplified|bbb|triggered"
            )
            decisions.append(decision(game_id=i, game_order=i, context=ctx, cp_loss=5.0))

        patterns = detect_context_patterns(decisions)
        assert len(patterns) == 2
        assert {p.context_signature for p in patterns} == {
            "opening|level|complex|aaa|self-initiated",
            "endgame|behind_slight|simplified|bbb|triggered",
        }

    def test_evidence_payload_is_self_contained(self):
        decisions = self._series(error_orders={0, 1, 2, 10, 11, 12})
        pattern = detect_context_patterns(decisions)[0]
        evidence = pattern.evidence
        assert evidence["occurrences"] == 6
        assert evidence["opportunities"] == 20
        assert evidence["occurrence_rate"] == round(6 / 20, 4)
        assert evidence["distinct_games"] == 6
        assert evidence["mean_cp_loss"] == 400.0
        assert "recent" in evidence and "older" in evidence
        # A claim must be re-derivable, so the thresholds travel with it.
        assert evidence["thresholds"]["min_opportunities"] == MIN_OPPORTUNITIES

    def test_trend_improving_when_recent_games_are_cleaner(self):
        """One recent error against four earlier ones, same denominator."""
        decisions = self._series(error_orders={0, 10, 11, 12, 13})
        pattern = detect_context_patterns(decisions)[0]
        assert pattern.trend_direction == "improving"

    def test_trend_persistent_when_rate_is_flat(self):
        decisions = self._series(error_orders={0, 1, 2, 10, 11, 12})
        pattern = detect_context_patterns(decisions)[0]
        assert pattern.trend_direction == "persistent"

    def test_trend_worsening_when_recent_games_are_worse(self):
        decisions = self._series(error_orders={0, 1, 2, 3, 10})
        pattern = detect_context_patterns(decisions)[0]
        assert pattern.trend_direction == "worsening"

    def test_trend_resolved_when_recent_games_are_clean(self):
        decisions = self._series(error_orders={10, 11, 12, 13})
        pattern = detect_context_patterns(decisions)[0]
        assert pattern.trend_direction == "resolved"

    def test_trend_new_when_only_recent_games_show_it(self):
        decisions = self._series(error_orders={0, 1, 2, 3, 4})
        pattern = detect_context_patterns(decisions)[0]
        assert pattern.trend_direction == "new"

    def test_occurrences_carry_position_and_decision(self):
        decisions = self._series(error_orders={0, 1, 2, 10, 11, 12})
        pattern = detect_context_patterns(decisions)[0]
        assert len(pattern.occurrences) == 6
        first = pattern.occurrences[0]
        assert first.game_id is not None
        assert first.context_description
        assert first.detector_metadata["context_signature"] == pattern.context_signature

    def test_detector_identity_is_recorded(self):
        decisions = self._series(error_orders={0, 1, 2, 10, 11, 12})
        pattern = detect_context_patterns(decisions)[0]
        assert pattern.detector_id
        assert pattern.detector_version == 1
        assert pattern.is_strength is False


class TestStrengthDetection:
    def test_solid_phase_becomes_a_strength(self):
        decisions = [
            decision(game_id=i, game_order=i, context="opening|x", phase="opening", cp_loss=5.0)
            for i in range(30)
        ]
        decisions.append(
            decision(
                game_id=99,
                game_order=99,
                context="opening|x",
                phase="opening",
                event_types=("opening_deviation",),
                cp_loss=200.0,
            )
        )
        strengths = detect_strengths(decisions)
        assert len(strengths) == 1
        strength = strengths[0]
        assert strength.is_strength is True
        assert strength.pattern_type == "phase_strength"
        assert strength.opportunity_count == 31
        assert strength.evidence["significant_errors"] == 1

    def test_weak_phase_is_not_a_strength(self):
        decisions = [
            decision(
                game_id=i,
                game_order=i,
                context="endgame|x",
                phase="endgame",
                event_types=("endgame_technique_failure",) if i % 4 == 0 else (),
                cp_loss=200.0 if i % 4 == 0 else 5.0,
            )
            for i in range(30)
        ]
        assert detect_strengths(decisions) == []

    def test_thin_phase_is_not_a_strength(self):
        decisions = [
            decision(game_id=i, game_order=i, context="a|x", phase="opening", cp_loss=5.0)
            for i in range(5)
        ]
        assert detect_strengths(decisions) == []
