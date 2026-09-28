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
    SOURCE_SYSTEM,
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


class TestSystemRecordedCoaching:
    """The ledger must fill from what the product did, not from a model's account.

    Before this, the only writer was an authenticated POST that nothing called, so
    in production the ledger stayed empty and both the "coaching already given"
    context block and the profile's coaching history could never populate.
    """

    def _pattern(self, db, user, subtype: str = SUBTYPE, context: str = CONTEXT):
        from app.models.pattern import PlayerPattern

        row = PlayerPattern(
            user_id=user.id,
            pattern_type="weakness",
            pattern_subtype=subtype,
            context_signature=context,
            severity="high",
            confidence_score=0.9,
            occurrence_count=5,
            affected_games_count=4,
            affected_games_ratio=0.5,
            pattern_description="Recurring pattern: an endgame technique error.",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def test_plan_records_the_pattern_it_targets(self, db, coach_user):
        from app.services.training.training_plan_service import create_manual_plan

        pattern = self._pattern(db, coach_user)
        plan = create_manual_plan(
            db,
            coach_user.id,
            title="Rook endings",
            drills=[{"prompt_text": "Convert this ending", "pattern_id": pattern.id}],
            focus_pattern_ids=[pattern.id],
        )

        rows = db.query(CoachingIntervention).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.source == SOURCE_SYSTEM
        assert row.pattern_id == pattern.id
        # The descriptive fields are copied, so the outcome stays measurable even
        # after the pattern row is pruned.
        assert row.pattern_subtype == SUBTYPE
        assert row.context_signature == CONTEXT
        assert row.payload["plan_id"] == plan.id

    def test_a_second_plan_on_the_same_pattern_is_not_a_second_intervention(self, db, coach_user):
        from app.services.training.training_plan_service import create_manual_plan

        pattern = self._pattern(db, coach_user)
        for _ in range(2):
            create_manual_plan(
                db,
                coach_user.id,
                title="Rook endings",
                drills=[{"prompt_text": "Convert this ending", "pattern_id": pattern.id}],
                focus_pattern_ids=[pattern.id],
            )
        assert db.query(CoachingIntervention).count() == 1

    def test_a_new_attempt_is_recorded_once_the_last_one_settled(self, db, coach_user):
        from app.services.training.training_plan_service import create_manual_plan

        pattern = self._pattern(db, coach_user)
        create_manual_plan(
            db,
            coach_user.id,
            title="Rook endings",
            drills=[{"prompt_text": "Convert this ending", "pattern_id": pattern.id}],
            focus_pattern_ids=[pattern.id],
        )
        db.query(CoachingIntervention).one().outcome = OUTCOME_RESOLVED
        db.commit()

        create_manual_plan(
            db,
            coach_user.id,
            title="Rook endings again",
            drills=[{"prompt_text": "Convert this ending", "pattern_id": pattern.id}],
            focus_pattern_ids=[pattern.id],
        )
        assert db.query(CoachingIntervention).count() == 2

    def test_a_plan_without_a_pattern_records_nothing(self, db, coach_user):
        """An intervention that can never be measured is noise in the ledger."""
        from app.services.training.training_plan_service import create_manual_plan

        create_manual_plan(
            db,
            coach_user.id,
            title="General work",
            drills=[{"prompt_text": "Play a slow game"}],
        )
        assert db.query(CoachingIntervention).count() == 0

    def test_saved_drill_records_an_intervention(self, db, coach_user):
        from app.services.training.training_plan_service import create_adhoc_drill

        pattern = self._pattern(db, coach_user)
        drill = create_adhoc_drill(
            db,
            coach_user.id,
            drill_type="puzzle",
            prompt_text="Find the winning continuation",
            pattern_id=pattern.id,
        )

        row = db.query(CoachingIntervention).one()
        assert row.pattern_id == pattern.id
        assert row.payload["drill_id"] == drill.id

    def test_generated_plan_records_by_its_own_path(self, db, coach_user, monkeypatch):
        """The generator builds plan rows directly, so it needs its own hook."""
        from app.services.training import drill_generator_service as generator

        pattern = self._pattern(db, coach_user)
        monkeypatch.setattr(generator, "select_patterns_for_drills", lambda *a, **k: [pattern])
        monkeypatch.setattr(generator, "pick_best_occurrence", lambda *a, **k: None)

        plan = generator.generate_training_plan(db, coach_user.id)
        assert plan is not None

        row = db.query(CoachingIntervention).one()
        assert row.pattern_id == pattern.id
        assert row.payload["generator"] == "drill_generator_service"

    def test_legacy_pattern_is_recorded_but_never_measurable(self, db, coach_user, pivot):
        """A pattern from the old engine has no context to measure against.

        Recording it is still correct — the coaching happened — but the outcome
        stays ``unknown`` with a reason instead of being guessed. Worth pinning:
        production still holds these rows, so the honest answer must be visible.
        """
        from app.services.training.training_plan_service import create_manual_plan

        pattern = self._pattern(
            db,
            coach_user,
            subtype="endgame_major_swings",
            context=None,
        )
        create_manual_plan(
            db,
            coach_user.id,
            title="Legacy pattern work",
            drills=[{"prompt_text": "Work on endgames", "pattern_id": pattern.id}],
            focus_pattern_ids=[pattern.id],
        )

        row = db.query(CoachingIntervention).one()
        result = evaluate_intervention_outcome(
            row,
            series(games_before=5, errors_before=5, games_after=5, errors_after=0, pivot=pivot),
        )
        assert result["outcome"] == OUTCOME_UNKNOWN
        assert "measurable pattern" in result["reason"]

    def test_recorded_intervention_is_measurable_end_to_end(self, db, coach_user, pivot):
        """The point of recording: the outcome can actually be computed later."""
        from app.services.training.training_plan_service import create_manual_plan

        pattern = self._pattern(db, coach_user)
        create_manual_plan(
            db,
            coach_user.id,
            title="Rook endings",
            drills=[{"prompt_text": "Convert this ending", "pattern_id": pattern.id}],
            focus_pattern_ids=[pattern.id],
        )
        row = db.query(CoachingIntervention).one()
        row.offered_at = pivot
        db.commit()

        decisions = series(
            games_before=5, errors_before=5, games_after=5, errors_after=0, pivot=pivot
        )
        result = evaluate_intervention_outcome(row, decisions)
        assert result["outcome"] == OUTCOME_RESOLVED
        assert result["evidence"]["before"]["occurrences"] == 5


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
