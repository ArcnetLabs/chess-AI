"""Tests for pattern persistence cost, idempotence, and replacement semantics.

Found by running the real entry point: a pattern run took **504 seconds** and issued
**2,172 SQL statements** for 37 patterns, because every occurrence was looked up with
its own SELECT and every stored row was re-assigned (marking it dirty) whether or not
anything had changed. Against a pooled remote database at ~230 ms per statement that
is minutes of wall time after *every* analysis batch.

These tests pin the properties that fix depends on: a re-run with unchanged data
writes nothing, and the statement count does not scale with the number of occurrences.

The second half pins the other half of the contract: a run's stored occurrences must
equal what that run detected. Upserting alone left rows behind whose games no longer
qualified — occurrences that contradicted their own pattern's ``affected_games_count``,
which is the number shown to the player and handed to the coach as evidence.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event

from app.models.game import Game
from app.models.pattern import PatternOccurrence, PatternRun, PlayerPattern
from app.models.user import User
from app.services.patterns import pattern_service
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


# ---------------------------------------------------------------------------
# A run replaces what it detected
# ---------------------------------------------------------------------------


def _user(db, *, email: str = "persist@example.com", sub: str = "persist-sub") -> User:
    user = User(
        email=email,
        supabase_user_id=sub,
        connection_type="username_only",
        current_ratings={"rapid": 1500},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _games(db, user: User, count: int) -> list[Game]:
    games = []
    for index in range(count):
        game = Game(
            user_id=user.id,
            chesscom_game_id=f"persist-{user.id}-{index}",
            is_analyzed=True,
            end_time=datetime.now(timezone.utc) - timedelta(days=index),
        )
        db.add(game)
        games.append(game)
    db.commit()
    for game in games:
        db.refresh(game)
    return games


def _phase_occurrence(game_id: int, *, move_number: int = 0) -> PatternOccurrenceInput:
    return PatternOccurrenceInput(
        game_id=game_id,
        move_number=move_number,
        game_phase="endgame",
        context_description="An endgame where you lost ground",
        detector_metadata={"phase_acpl": 45.0, "threshold": 40.0},
    )


def _pattern(
    subtype: str,
    game_ids: list[int],
    *,
    detector_id: str | None = None,
    pattern_type: str = "phase_weakness",
) -> DetectedPattern:
    occurrences = [_phase_occurrence(game_id) for game_id in game_ids]
    return DetectedPattern(
        pattern_type=pattern_type,
        pattern_subtype=subtype,
        severity="high",
        confidence_score=0.8,
        occurrence_count=len(occurrences),
        affected_games_count=len(occurrences),
        affected_games_ratio=0.5,
        pattern_description="Your endgames are where you give ground.",
        occurrences=occurrences,
        detector_id=detector_id,
    )


def _run_of(patterns: list[DetectedPattern], considered: list[int]) -> PatternRunResult:
    return PatternRunResult(
        user_id=1,
        patterns=patterns,
        games_considered=len(considered),
        considered_game_ids=list(considered),
    )


def _stored(db) -> set[tuple[str, int, int]]:
    """Every stored occurrence as ``(pattern_subtype, game_id, move_number)``."""
    rows = (
        db.query(
            PlayerPattern.pattern_subtype,
            PatternOccurrence.game_id,
            PatternOccurrence.move_number,
        )
        .join(PatternOccurrence, PatternOccurrence.pattern_id == PlayerPattern.id)
        .all()
    )
    return {(subtype, game_id, move) for subtype, game_id, move in rows}


def test_a_rerun_removes_occurrences_it_no_longer_produces(db):
    """The defect: the games that stopped qualifying must not stay behind.

    Persistence only upserted, so a corrected analysis left occurrences whose own
    pattern reported a smaller ``affected_games_count`` — the number a player is
    shown. Occurrence rows and that count must agree after every run.
    """
    user = _user(db)
    games = _games(db, user, 4)
    game_ids = [game.id for game in games]

    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", game_ids)], game_ids)
    )
    assert _stored(db) == {("high_endgame_acpl", game_id, 0) for game_id in game_ids}

    # Re-detection after the data was corrected: the last two games no longer
    # clear the threshold, so the detector no longer emits them.
    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", game_ids[:2])], game_ids)
    )

    assert _stored(db) == {
        ("high_endgame_acpl", game_ids[0], 0),
        ("high_endgame_acpl", game_ids[1], 0),
    }
    pattern = db.query(PlayerPattern).filter(PlayerPattern.user_id == user.id).one()
    assert pattern.affected_games_count == 2
    assert (
        db.query(PatternOccurrence).filter(PatternOccurrence.pattern_id == pattern.id).count()
        == pattern.affected_games_count
    )


def test_occurrences_outside_the_run_game_scope_survive(db):
    """A ``game_limit`` run considered recent games only, so only those are its to delete."""
    user = _user(db)
    games = _games(db, user, 5)
    game_ids = [game.id for game in games]

    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", game_ids)], game_ids)
    )

    # A limited rerun over the two most recent games. It re-detects only the
    # older of those two, so the newer one's row goes — but the three games it
    # never looked at keep their occurrences.
    recent = [game_ids[3], game_ids[4]]
    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", [game_ids[3]])], recent)
    )

    assert _stored(db) == {
        ("high_endgame_acpl", game_ids[0], 0),
        ("high_endgame_acpl", game_ids[1], 0),
        ("high_endgame_acpl", game_ids[2], 0),
        ("high_endgame_acpl", game_ids[3], 0),
    }


def test_occurrences_of_patterns_the_run_did_not_evaluate_survive(db):
    """Only patterns present in the result are replaced; others are not this run's."""
    user = _user(db)
    games = _games(db, user, 3)
    game_ids = [game.id for game in games]

    persist_pattern_snapshots(
        db,
        user.id,
        _run_of(
            [
                _pattern("high_endgame_acpl", game_ids),
                _pattern("high_middlegame_acpl", game_ids),
            ],
            game_ids,
        ),
    )

    # A run that evaluated only the endgame pattern — the middlegame detector was
    # not part of it, so its occurrences must all survive untouched.
    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", game_ids[:1])], game_ids)
    )

    assert _stored(db) == {
        ("high_endgame_acpl", game_ids[0], 0),
        ("high_middlegame_acpl", game_ids[0], 0),
        ("high_middlegame_acpl", game_ids[1], 0),
        ("high_middlegame_acpl", game_ids[2], 0),
    }


def test_a_row_carrying_another_user_id_is_never_touched(db):
    """Defence in depth: a row that is not this user's is left alone, in scope or not."""
    user = _user(db)
    other = _user(db, email="other@example.com", sub="other-sub")
    games = _games(db, user, 2)
    game_ids = [game.id for game in games]

    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", game_ids)], game_ids)
    )
    pattern = db.query(PlayerPattern).filter(PlayerPattern.user_id == user.id).one()
    # A row hanging off this user's pattern but stamped with another user's id. Its
    # (pattern, game, move) triple is one this run does not produce, so only the
    # user check stands between it and removal.
    foreign = PatternOccurrence(
        pattern_id=pattern.id,
        user_id=other.id,
        game_id=game_ids[1],
        move_number=99,
    )
    db.add(foreign)
    db.commit()

    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", [game_ids[0]])], game_ids)
    )

    remaining = db.query(PatternOccurrence).filter(PatternOccurrence.id == foreign.id).all()
    assert len(remaining) == 1, "another user's row was deleted"


def test_a_pattern_pruned_in_the_same_run_loses_its_occurrences_once(db):
    """Removal by cascade, not twice: the stale counter must not claim them."""
    user = _user(db)
    games = _games(db, user, 2)
    game_ids = [game.id for game in games]

    persist_pattern_snapshots(
        db,
        user.id,
        _run_of(
            [
                _pattern("high_endgame_acpl", [game_ids[0]]),
                _pattern(
                    "major_blunder__middlegame|level|complex|self-initiated",
                    game_ids,
                    detector_id="event_context",
                    pattern_type="decision_pattern",
                ),
                _pattern(
                    "tactical_miss__middlegame|level|complex|self-initiated",
                    [game_ids[0]],
                    detector_id="event_context",
                    pattern_type="decision_pattern",
                ),
            ],
            game_ids,
        ),
    )
    pruned = (
        db.query(PlayerPattern)
        .filter(PlayerPattern.pattern_subtype.like("major_blunder%"))
        .one()
    )

    # The event detector no longer fires the blunder pattern, so the run prunes the
    # pattern row itself while replacing the occurrences of the patterns it kept.
    persist_pattern_snapshots(
        db,
        user.id,
        _run_of(
            [
                _pattern("high_endgame_acpl", [game_ids[0]]),
                _pattern(
                    "tactical_miss__middlegame|level|complex|self-initiated",
                    [game_ids[0]],
                    detector_id="event_context",
                    pattern_type="decision_pattern",
                ),
            ],
            game_ids,
        ),
    )

    assert db.query(PatternOccurrence).filter(PatternOccurrence.pattern_id == pruned.id).count() == 0
    assert _stored(db) == {
        ("high_endgame_acpl", game_ids[0], 0),
        ("tactical_miss__middlegame|level|complex|self-initiated", game_ids[0], 0),
    }
    run = db.query(PatternRun).order_by(PatternRun.id.desc()).first()
    assert run.summary["stale_occurrences_removed"] == 0
    assert run.summary["pruned"] == 1


def test_a_run_that_raises_after_the_write_leaves_the_stored_set_intact(db, monkeypatch):
    """The removal shares the upsert's transaction, so a failed run changes nothing."""
    user = _user(db)
    games = _games(db, user, 3)
    game_ids = [game.id for game in games]

    persist_pattern_snapshots(
        db, user.id, _run_of([_pattern("high_endgame_acpl", game_ids)], game_ids)
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("detection run failed after the occurrence write")

    monkeypatch.setattr(pattern_service, "_record_run", _boom)
    with pytest.raises(RuntimeError):
        persist_pattern_snapshots(
            db, user.id, _run_of([_pattern("high_endgame_acpl", [game_ids[0]])], game_ids)
        )

    db.rollback()

    assert _stored(db) == {("high_endgame_acpl", game_id, 0) for game_id in game_ids}

