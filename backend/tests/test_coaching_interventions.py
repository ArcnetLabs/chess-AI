"""Tests for coaching memory: recording interventions and measuring outcomes.

The properties that matter:

* an outcome is measured from later games, never asserted;
* too little evidence yields ``unknown`` rather than a hopeful verdict;
* "resolved" requires the pattern to have actually stopped, with enough games;
* an intervention whose pattern was never present is not called a success;
* records survive pattern pruning (the pattern link may go, the history may not).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.coaching_intervention import CoachingIntervention
from app.services.coaching.interventions import (
    INTERVENTION_CONCEPT,
    INTERVENTION_DRILL,
    MIN_GAMES_AFTER,
    OUTCOME_IMPROVING,
    OUTCOME_PERSISTENT,
    OUTCOME_RESOLVED,
    OUTCOME_UNKNOWN,
    OUTCOME_WORSENED,
    coaching_history_summary,
    evaluate_intervention_outcome,
    evaluate_intervention_outcomes,
    list_interventions,
    record_intervention,
)
from app.services.patterns.event_pattern_detector import Decision

CONTEXT = "endgame|level|complex|triggered"
SUBTYPE = f"endgame_technique_failure__{CONTEXT}"


def decision(
    *,
    game_id: int,
    end_time: datetime,
    is_error: bool,
    context: str = CONTEXT,
) -> Decision:
    return Decision(
        game_id=game_id,
        game_order=game_id,
        game_end_time=end_time,
        event_types=("endgame_technique_failure",) if is_error else (),
        serious_event_types=("endgame_technique_failure",) if is_error else (),
        phase="endgame",
        context=context,
        cp_loss=300.0 if is_error else 0.0,
    )


def series(
    *, games_before: int, errors_before: int, games_after: int, errors_after: int, pivot: datetime
) -> list[Decision]:
    decisions: list[Decision] = []
    for index in range(games_before):
        decisions.append(
            decision(
                game_id=index,
                end_time=pivot - timedelta(days=index + 1),
                is_error=index < errors_before,
            )
        )
    for index in range(games_after):
        decisions.append(
            decision(
                game_id=100 + index,
                end_time=pivot + timedelta(days=index + 1),
                is_error=index < errors_after,
            )
        )
    return decisions


@pytest.fixture
def pivot() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=10)


@pytest.fixture
def coach_user(db):
    """A local user row: interventions are per-user and ownership-checked."""
    from app.models.user import User

    user = User(
        supabase_user_id="interventions-test-user",
        email="interventions@chessrun.local",
        chesscom_username="interventions_tester",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class Intervention:
    """Stand-in for a stored intervention."""

    def __init__(self, pivot: datetime, subtype: str = SUBTYPE):
        self.pattern_subtype = subtype
        self.offered_at = pivot


class TestOutcomeMeasurement:
    def test_improving_when_the_rate_drops(self, pivot):
        decisions = series(
            games_before=5, errors_before=5, games_after=5, errors_after=1, pivot=pivot
        )
        result = evaluate_intervention_outcome(Intervention(pivot), decisions)
        assert result["outcome"] == OUTCOME_IMPROVING
        assert result["evidence"]["before"]["rate"] == 1.0
        assert result["evidence"]["after"]["rate"] == 0.2

    def test_resolved_when_the_pattern_stops(self, pivot):
        decisions = series(
            games_before=5, errors_before=4, games_after=4, errors_after=0, pivot=pivot
        )
        result = evaluate_intervention_outcome(Intervention(pivot), decisions)
        assert result["outcome"] == OUTCOME_RESOLVED
        assert result["evidence"]["after"]["occurrences"] == 0

    def test_persistent_when_nothing_changes(self, pivot):
        decisions = series(
            games_before=5, errors_before=5, games_after=5, errors_after=5, pivot=pivot
        )
        result = evaluate_intervention_outcome(Intervention(pivot), decisions)
        assert result["outcome"] == OUTCOME_PERSISTENT

    def test_worsening_when_the_rate_rises(self, pivot):
        decisions = series(
            games_before=10, errors_before=2, games_after=5, errors_after=5, pivot=pivot
        )
        result = evaluate_intervention_outcome(Intervention(pivot), decisions)
        assert result["outcome"] == OUTCOME_WORSENED

    def test_too_few_later_games_is_unknown(self, pivot):
        decisions = series(
            games_before=6, errors_before=6, games_after=MIN_GAMES_AFTER - 1,
            errors_after=0, pivot=pivot,
        )
        result = evaluate_intervention_outcome(Intervention(pivot), decisions)
        assert result["outcome"] == OUTCOME_UNKNOWN
        assert "not enough games" in result["reason"]

    def test_no_pattern_before_is_not_reported_as_success(self, pivot):
        """A pattern that was never present cannot have been fixed."""
        decisions = series(
            games_before=5, errors_before=0, games_after=5, errors_after=0, pivot=pivot
        )
        result = evaluate_intervention_outcome(Intervention(pivot), decisions)
        assert result["outcome"] == OUTCOME_UNKNOWN
        assert "no occurrences before" in result["evidence"].get("note", "")

    def test_unmeasurable_intervention_is_unknown(self, pivot):
        result = evaluate_intervention_outcome(
            Intervention(pivot, subtype="phase_weakness/high_endgame_acpl"), []
        )
        assert result["outcome"] == OUTCOME_UNKNOWN

    def test_other_contexts_are_not_counted(self, pivot):
        decisions = series(
            games_before=5, errors_before=5, games_after=5, errors_after=0, pivot=pivot
        )
        decisions.extend(
            decision(
                game_id=200 + index,
                end_time=pivot + timedelta(days=index + 1),
                is_error=True,
                context="opening|level|complex|self_initiated",
            )
            for index in range(5)
        )
        result = evaluate_intervention_outcome(Intervention(pivot), decisions)
        # The unrelated opening decisions must not appear in the after-window.
        assert result["evidence"]["after"]["opportunities"] == 5
        assert result["outcome"] == OUTCOME_RESOLVED


class TestPersistence:
    def test_records_and_lists(self, db, coach_user):
        record_intervention(
            db,
            coach_user.id,
            intervention_type=INTERVENTION_DRILL,
            pattern_subtype=SUBTYPE,
            title="Rook endgame technique",
        )
        rows = list_interventions(db, coach_user.id)
        assert len(rows) == 1
        assert rows[0].outcome == OUTCOME_UNKNOWN
        assert rows[0].source == "coach"

    def test_unknown_type_is_rejected(self, db, coach_user):
        with pytest.raises(ValueError):
            record_intervention(
                db, coach_user.id, intervention_type="interpretive_dance"
            )

    def test_history_summary_is_compact(self, db, coach_user):
        record_intervention(
            db,
            coach_user.id,
            intervention_type=INTERVENTION_CONCEPT,
            pattern_subtype=SUBTYPE,
            title="Converting winning positions",
        )
        history = coaching_history_summary(db, coach_user.id)
        assert history[0]["intervention_type"] == INTERVENTION_CONCEPT
        assert history[0]["outcome"] == OUTCOME_UNKNOWN

    def test_pattern_link_is_nullable_for_history(self, db, coach_user):
        """Pruning a pattern must not erase the record that coaching happened."""
        row = record_intervention(
            db,
            coach_user.id,
            intervention_type=INTERVENTION_DRILL,
            pattern_subtype=SUBTYPE,
        )
        assert row.pattern_id is None  # no pattern was supplied
        assert db.query(CoachingIntervention).count() == 1

    def test_outcome_evaluation_skips_settled_rows(self, db, coach_user, monkeypatch):
        row = record_intervention(
            db,
            coach_user.id,
            intervention_type=INTERVENTION_DRILL,
            pattern_subtype=SUBTYPE,
        )
        row.outcome = OUTCOME_RESOLVED
        db.commit()

        called = {"count": 0}
        monkeypatch.setattr(
            "app.services.coaching.interventions.load_decisions",
            lambda *args, **kwargs: called.__setitem__("count", called["count"] + 1) or [],
        )
        counts = evaluate_intervention_outcomes(db, coach_user.id)
        # Only resolved/worsening rows are excluded, and an empty decision series
        # short-circuits before any measurement.
        assert counts == {}
        assert called["count"] == 0
