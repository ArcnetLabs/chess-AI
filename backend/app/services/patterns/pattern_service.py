"""Persist pattern snapshots to ``player_patterns`` / ``pattern_occurrences``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.pattern import PatternOccurrence, PatternRun, PlayerPattern

from .types import DetectedPattern, PatternOccurrenceInput, PatternRunResult


def _upsert_player_pattern(
    db: Session,
    user_id: int,
    detected: DetectedPattern,
    existing: Optional[PlayerPattern],
) -> PlayerPattern:
    now = datetime.now(timezone.utc)
    severity_value = (
        detected.severity.value
        if hasattr(detected.severity, "value")
        else str(detected.severity)
    )
    context_fields = {
        "evidence": detected.evidence or None,
        "context_signature": detected.context_signature,
        "opportunity_count": detected.opportunity_count,
        "occurrence_rate": detected.occurrence_rate,
        "detector_id": detected.detector_id,
        "detector_version": detected.detector_version,
    }

    if existing:
        existing.severity = severity_value
        existing.confidence_score = detected.confidence_score
        existing.occurrence_count = detected.occurrence_count
        existing.affected_games_count = detected.affected_games_count
        existing.affected_games_ratio = detected.affected_games_ratio
        existing.pattern_description = detected.pattern_description
        existing.example_positions = detected.example_positions or None
        existing.last_seen_at = now
        existing.trend_direction = detected.trend_direction
        existing.is_strength = detected.is_strength
        existing.recommended_drill_type = detected.recommended_drill_type
        for key, value in context_fields.items():
            setattr(existing, key, value)
        return existing

    row = PlayerPattern(
        user_id=user_id,
        pattern_type=detected.pattern_type,
        pattern_subtype=detected.pattern_subtype,
        severity=severity_value,
        confidence_score=detected.confidence_score,
        occurrence_count=detected.occurrence_count,
        affected_games_count=detected.affected_games_count,
        affected_games_ratio=detected.affected_games_ratio,
        pattern_description=detected.pattern_description,
        example_positions=detected.example_positions or None,
        first_seen_at=now,
        last_seen_at=now,
        trend_direction=detected.trend_direction,
        is_strength=detected.is_strength,
        recommended_drill_type=detected.recommended_drill_type,
        **context_fields,
    )
    db.add(row)
    return row


_OCCURRENCE_FIELDS = (
    "game_phase",
    "fen_before",
    "fen_after",
    "user_move",
    "best_move",
    "user_eval",
    "best_eval",
    "eval_delta",
    "context_description",
    "detector_metadata",
    "move_id",
    "event_id",
)


def _apply_occurrence(existing: PatternOccurrence, occurrence: PatternOccurrenceInput) -> bool:
    """Copy a detected occurrence onto a stored row, and report whether it changed.

    Only genuinely different fields are assigned. Assigning unconditionally marks the
    row dirty, so a re-run with identical data emitted an UPDATE per occurrence — half
    of the statements an already slow run was making.
    """
    metadata = occurrence.detector_metadata or {}
    desired = {
        "game_phase": occurrence.game_phase,
        "fen_before": occurrence.fen_before,
        "fen_after": occurrence.fen_after,
        "user_move": occurrence.user_move,
        "best_move": occurrence.best_move,
        "user_eval": occurrence.user_eval,
        "best_eval": occurrence.best_eval,
        "eval_delta": occurrence.eval_delta,
        "context_description": occurrence.context_description,
        "detector_metadata": occurrence.detector_metadata,
        "move_id": metadata.get("move_id"),
        "event_id": metadata.get("event_id"),
    }
    changed = False
    for field, value in desired.items():
        if getattr(existing, field) != value:
            setattr(existing, field, value)
            changed = True
    return changed


def _persist_occurrences(
    db: Session,
    pattern_id: int,
    user_id: int,
    occurrences: Sequence[PatternOccurrenceInput],
    known: Dict[Tuple[int, int, int], PatternOccurrence],
) -> Tuple[int, int]:
    """Write one pattern's occurrences, reusing rows already loaded.

    ``known`` is keyed ``(pattern_id, game_id, move_number)`` and shared across the
    whole run, so this costs no queries: the previous version issued one SELECT per
    occurrence, which is what made a pattern run take minutes against a pooled remote
    database instead of seconds.
    """
    written = unchanged = 0
    for occurrence in occurrences:
        if occurrence.game_id <= 0:
            continue
        key = (pattern_id, occurrence.game_id, occurrence.move_number)
        existing = known.get(key)
        if existing is not None:
            if _apply_occurrence(existing, occurrence):
                written += 1
            else:
                unchanged += 1
            continue

        metadata = occurrence.detector_metadata or {}
        row = PatternOccurrence(
            pattern_id=pattern_id,
            user_id=user_id,
            game_id=occurrence.game_id,
            move_number=occurrence.move_number,
            game_phase=occurrence.game_phase,
            fen_before=occurrence.fen_before,
            fen_after=occurrence.fen_after,
            user_move=occurrence.user_move,
            best_move=occurrence.best_move,
            user_eval=occurrence.user_eval,
            best_eval=occurrence.best_eval,
            eval_delta=occurrence.eval_delta,
            context_description=occurrence.context_description,
            detector_metadata=occurrence.detector_metadata,
            move_id=metadata.get("move_id"),
            event_id=metadata.get("event_id"),
        )
        db.add(row)
        known[key] = row
        written += 1
    return written, unchanged


def persist_pattern_snapshots(
    db: Session,
    user_id: int,
    result: PatternRunResult,
) -> List[PlayerPattern]:
    """
    Upsert detected patterns and idempotent occurrence rows.

    Designed for Celery retry safety: unique constraints prevent duplicate
    pattern keys and occurrence (pattern_id, game_id, move_number) tuples.

    Patterns produced by the context-aware detector that no longer fire are
    removed. Without that, a weakness the player has fixed would stay on their
    profile forever, which is the opposite of a longitudinal coach.
    """
    saved: List[PlayerPattern] = []

    # One query for every occurrence this run could touch, instead of one per
    # occurrence. The pattern rows are upserted first because their ids key the map.
    known: Dict[Tuple[int, int, int], PatternOccurrence] = {}
    pattern_rows: List[Tuple[object, PlayerPattern]] = []
    for detected in result.patterns:
        existing = (
            db.query(PlayerPattern)
            .filter(
                PlayerPattern.user_id == user_id,
                PlayerPattern.pattern_type == detected.pattern_type,
                PlayerPattern.pattern_subtype == detected.pattern_subtype,
            )
            .first()
        )
        row = _upsert_player_pattern(db, user_id, detected, existing)
        db.flush()
        pattern_rows.append((detected, row))
        saved.append(row)

    pattern_ids = [row.id for _, row in pattern_rows]
    if pattern_ids:
        for stored in (
            db.query(PatternOccurrence)
            .filter(PatternOccurrence.pattern_id.in_(pattern_ids))
            .all()
        ):
            known[(stored.pattern_id, stored.game_id, stored.move_number)] = stored

    written = unchanged = 0
    for detected, row in pattern_rows:
        row_written, row_unchanged = _persist_occurrences(
            db, row.id, user_id, detected.occurrences, known
        )
        written += row_written
        unchanged += row_unchanged
    logger.debug(
        f"pattern occurrences for user_id={user_id}: {written} written, "
        f"{unchanged} already current"
    )

    removed = _prune_stale_event_patterns(db, user_id, result)
    _record_run(db, user_id, result, removed)

    db.commit()
    logger.info(
        f"Persisted {len(saved)} pattern snapshots for user_id={user_id} "
        f"(run patterns={result.pattern_count}, pruned={removed})"
    )
    return saved


def _prune_stale_event_patterns(
    db: Session,
    user_id: int,
    result: PatternRunResult,
) -> int:
    """Delete context-aware patterns this run no longer detects.

    Scoped to the detectors that actually ran in this result, so a run that only
    covered part of the history (or was limited by ``game_limit``) can never
    delete an unrelated detector's patterns.
    """
    detector_ids = {
        pattern.detector_id for pattern in result.patterns if pattern.detector_id
    }
    if not detector_ids:
        return 0

    survivors = {
        (pattern.pattern_type, pattern.pattern_subtype): True
        for pattern in result.patterns
        if pattern.detector_id
    }
    stale = (
        db.query(PlayerPattern)
        .filter(
            PlayerPattern.user_id == user_id,
            PlayerPattern.detector_id.in_(detector_ids),
        )
        .all()
    )
    removed = 0
    for row in stale:
        if (row.pattern_type, row.pattern_subtype) not in survivors:
            db.delete(row)  # occurrences cascade
            removed += 1
    return removed


def _record_run(
    db: Session,
    user_id: int,
    result: PatternRunResult,
    pruned: int,
) -> None:
    """Append a row describing what this detection run saw."""
    strengths = sum(1 for pattern in result.patterns if pattern.is_strength)
    db.add(
        PatternRun(
            user_id=user_id,
            detector_version=result.detector_version,
            games_considered=result.games_considered,
            decisions_considered=result.decisions_considered,
            patterns_detected=result.pattern_count - strengths,
            strengths_detected=strengths,
            summary={
                "pruned": pruned,
                "types": sorted({p.pattern_type for p in result.patterns}),
                "trends": sorted(
                    {p.trend_direction for p in result.patterns if p.trend_direction}
                ),
            },
        )
    )


def list_user_patterns(
    db: Session,
    user_id: int,
    *,
    skip: int = 0,
    limit: int = 50,
) -> List[PlayerPattern]:
    """Return persisted pattern rows for a user, newest first."""
    return (
        db.query(PlayerPattern)
        .filter(PlayerPattern.user_id == user_id)
        .order_by(PlayerPattern.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
