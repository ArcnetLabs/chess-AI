"""Persist pattern snapshots to ``player_patterns`` / ``pattern_occurrences``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.pattern import PatternOccurrence, PlayerPattern

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
    )
    db.add(row)
    return row


def _persist_occurrence(
    db: Session,
    pattern_id: int,
    user_id: int,
    occurrence: PatternOccurrenceInput,
) -> None:
    if occurrence.game_id <= 0:
        return

    existing = (
        db.query(PatternOccurrence)
        .filter(
            PatternOccurrence.pattern_id == pattern_id,
            PatternOccurrence.game_id == occurrence.game_id,
            PatternOccurrence.move_number == occurrence.move_number,
        )
        .first()
    )
    if existing:
        existing.game_phase = occurrence.game_phase
        existing.context_description = occurrence.context_description
        existing.detector_metadata = occurrence.detector_metadata
        return

    db.add(
        PatternOccurrence(
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
        )
    )


def persist_pattern_snapshots(
    db: Session,
    user_id: int,
    result: PatternRunResult,
) -> List[PlayerPattern]:
    """
    Upsert detected patterns and idempotent occurrence rows.

    Designed for Celery retry safety: unique constraints prevent duplicate
    pattern keys and occurrence (pattern_id, game_id, move_number) tuples.
    """
    saved: List[PlayerPattern] = []

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

        for occurrence in detected.occurrences:
            _persist_occurrence(db, row.id, user_id, occurrence)

        saved.append(row)

    db.commit()
    logger.info(
        f"Persisted {len(saved)} pattern snapshots for user_id={user_id} "
        f"(run patterns={result.pattern_count})"
    )
    return saved
