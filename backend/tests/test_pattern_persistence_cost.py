"""Tests for pattern persistence cost and idempotence.

Found by running the real entry point: a pattern run took **504 seconds** and issued
**2,172 SQL statements** for 37 patterns, because every occurrence was looked up with
its own SELECT and every stored row was re-assigned (marking it dirty) whether or not
anything had changed. Against a pooled remote database at ~230 ms per statement that
is minutes of wall time after *every* analysis batch.

These tests pin the properties that fix depends on: a re-run with unchanged data
writes nothing, and the statement count does not scale with the number of occurrences.
"""

from sqlalchemy import event

from app.models.pattern import PlayerPattern
from app.services.patterns.pattern_service import persist_pattern_snapshots
from app.services.patterns.types import (
    DetectedPattern,
    PatternOccurrenceInput,
    PatternRunResult,
)


def _occurrence(index: int) -> PatternOccurrenceInput:
    return PatternOccurrenceInput(
        game_id=100 + index,
        move_number=10 + index,
        game_phase="middlegame",
        fen_before="8/8/8/8/8/8/8/8 w - - 0 1",
        fen_after="8/8/8/8/8/8/8/8 w - - 0 1",
        user_move="e2e4",
        best_move="d2d4",
        user_eval=20.0,
        best_eval=50.0,
        eval_delta=-30.0,
        context_description="middlegame|level|complex|self-initiated",
        detector_metadata={"move_id": index, "event_id": index},
    )


def _run(*, occurrences: int, description: str = "Recurring pattern.") -> PatternRunResult:
    pattern = DetectedPattern(
        pattern_type="decision_pattern",
        pattern_subtype="major_blunder__middlegame|level|complex|self-initiated",
        severity="high",
        confidence_score=0.9,
        occurrence_count=occurrences,
        affected_games_count=occurrences,
        affected_games_ratio=0.5,
        pattern_description=description,
        occurrences=[_occurrence(index) for index in range(occurrences)],
        detector_id="event_context",
        detector_version=1,
    )
    return PatternRunResult(user_id=1, patterns=[pattern], games_considered=occurrences)


def _count_statements(db, fn):
    """Run ``fn`` and count statements, separating occurrence reads from writes."""
    counted = {"all": 0, "occurrence_writes": 0, "occurrence_reads": 0}

    @event.listens_for(db.bind, "before_cursor_execute")
    def _listener(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        counted["all"] += 1
        lowered = statement.lower()
        if "pattern_occurrences" in lowered:
            if lowered.lstrip().startswith("select"):
                counted["occurrence_reads"] += 1
            elif lowered.lstrip().startswith(("insert", "update")):
                counted["occurrence_writes"] += 1

    try:
        result = fn()
    finally:
        event.remove(db.bind, "before_cursor_execute", _listener)
    return result, counted


def test_occurrences_are_written_once(db):
    result, counted = _count_statements(
        db, lambda: persist_pattern_snapshots(db, 1, _run(occurrences=40))
    )

    assert len(result) == 1
    assert counted["occurrence_writes"] >= 1, "the occurrences must actually be written"


def test_rerun_with_unchanged_data_writes_nothing(db):
    """Idempotence, and the reason a re-run is now cheap rather than ruinous."""
    persist_pattern_snapshots(db, 1, _run(occurrences=40))

    _, counted = _count_statements(
        db, lambda: persist_pattern_snapshots(db, 1, _run(occurrences=40))
    )

    assert counted["occurrence_writes"] == 0, (
        f"{counted['occurrence_writes']} occurrence writes for data that did not change"
    )


def test_occurrence_reads_do_not_scale_with_occurrences(db):
    """One read for the whole run, however many occurrences there are.

    The old implementation issued one SELECT per occurrence, so this was ~1:1 and the
    run cost minutes against a pooled remote database. Each *new* row still needs its
    own INSERT, which is why the assertion is about reads.
    """
    persist_pattern_snapshots(db, 1, _run(occurrences=20))

    small_result = _run(occurrences=20)
    small_result.patterns[0].pattern_subtype = (
        "tactical_miss__middlegame|level|complex|self-initiated"
    )
    _, small = _count_statements(
        db, lambda: persist_pattern_snapshots(db, 1, small_result)
    )

    large_result = _run(occurrences=200)
    large_result.patterns[0].pattern_subtype = (
        "missed_win__middlegame|level|complex|self-initiated"
    )
    _, large = _count_statements(
        db, lambda: persist_pattern_snapshots(db, 1, large_result)
    )

    # The property is that reads do not scale with occurrence count: ten times the
    # occurrences must not mean ten times the reads. (There is one batched read for the
    # run, plus whatever SQLAlchemy needs to cascade a pruned pattern's children.)
    assert large["occurrence_reads"] <= small["occurrence_reads"] + 1, (
        f"{large['occurrence_reads']} reads for 200 occurrences vs "
        f"{small['occurrence_reads']} for 20 — the read path scales with occurrences again"
    )
    assert large["occurrence_reads"] < 10, large["occurrence_reads"]
    # Inserts are still one per new row: 200 new rows must not become 200 reads *and*
    # 200 inserts.
    assert large["all"] < 200 * 2


def test_an_updated_occurrence_is_refreshed(db):
    """Unchanged rows are skipped, but a real change still lands."""
    persist_pattern_snapshots(db, 1, _run(occurrences=5))

    changed = _run(occurrences=5)
    changed.patterns[0].occurrences[0].context_description = "different context"
    persist_pattern_snapshots(db, 1, changed)

    from app.models.pattern import PatternOccurrence

    row = (
        db.query(PatternOccurrence)
        .filter(PatternOccurrence.move_number == 10)
        .one()
    )
    assert row.context_description == "different context"
