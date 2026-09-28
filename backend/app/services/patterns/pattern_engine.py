"""Pattern recognition orchestrator (P1-PR-01).

Coordinates data loading, deterministic detection, and optional persistence.
Does not call Stockfish or any LLM — reads only persisted analysis truth.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from .event_pattern_detector import detect_event_patterns
from .pattern_aggregator import build_pattern_run_result
from .pattern_data import load_pattern_aggregation_input
from .pattern_service import persist_pattern_snapshots
from .types import PatternRunResult

# Bumped when the set of detectors or their rules change, so a stored run can be
# interpreted later.
RUN_DETECTOR_VERSION = "pattern_engine_v2_events"


class PatternEngine:
    """
    Orchestrates the pattern aggregation pipeline.

    Two families of detectors run together:

    * the original label/aggregate detectors (phase ACPL, opening, blunder
      clusters), which read ``GameAnalysis`` rows;
    * the context-aware event detectors, which read ``chess_events`` and
      ``game_moves`` and group decisions by the situation that produced them.

    Both are deterministic and LLM-free. Celery tasks call
    ``run_pattern_detection`` — not inline logic.
    """

    def __init__(self, db: Session):
        self._db = db

    def detect(
        self,
        user_id: int,
        *,
        game_limit: Optional[int] = None,
        persist: bool = False,
    ) -> PatternRunResult:
        """
        Run deterministic pattern detection for a user.

        Args:
            user_id: Local user primary key.
            game_limit: Optional cap on recent analyzed games considered.
            persist: When True, upsert ``player_patterns`` / ``pattern_occurrences``.
        """
        data = load_pattern_aggregation_input(self._db, user_id, limit=game_limit)
        if data is None:
            logger.info(f"No analyzed games for pattern detection (user_id={user_id})")
            return PatternRunResult(user_id=user_id, patterns=[], games_considered=0)

        result = build_pattern_run_result(data)
        result.detector_version = RUN_DETECTOR_VERSION

        # Context-aware pass over the move/event layer. Failing here must not
        # lose the aggregate detectors' output, so it is contained.
        try:
            event_patterns, decisions = detect_event_patterns(
                self._db, user_id, game_limit=game_limit
            )
            result.patterns.extend(event_patterns)
            result.decisions_considered = decisions
        except Exception as exc:  # noqa: BLE001 - report, never break the run
            logger.error(
                f"Event pattern detection failed for user_id={user_id}: {exc}"
            )

        logger.info(
            f"Pattern detection user_id={user_id}: "
            f"{result.pattern_count} patterns from {result.games_considered} games "
            f"({result.decisions_considered} decisions)"
        )

        if persist and result.patterns:
            persist_pattern_snapshots(self._db, user_id, result)
            # Coaching outcomes track the newest games, so they are refreshed by
            # the same run that updates the patterns they refer to. Imported here
            # rather than at module scope: the interventions service reads the
            # decision series from this package, and a module-level import would
            # be circular. Failing here must not invalidate a detection run.
            try:
                from app.services.coaching.interventions import (
                    evaluate_intervention_outcomes,
                )

                evaluate_intervention_outcomes(self._db, user_id)
            except Exception as outcome_exc:  # noqa: BLE001
                logger.error(
                    f"Intervention outcome evaluation failed for user_id={user_id}: "
                    f"{outcome_exc}"
                )

            # Coaching memory: the practice focus offered to this player is
            # recorded here, because this is where the product knows coaching was
            # delivered. "Have I taught you this, and did it work?" is only
            # answerable if the offer is a stored fact rather than something a
            # model reports about itself. Duplicates are skipped by the ledger, so
            # this is safe on every run.
            try:
                from app.services.coaching.practice_focus import offer_practice_focus

                offer_practice_focus(self._db, user_id)
            except Exception as practice_exc:  # noqa: BLE001
                logger.error(
                    f"Practice focus failed for user_id={user_id}: {practice_exc}"
                )

        return result


def run_pattern_detection(
    db: Session,
    user_id: int,
    *,
    game_limit: Optional[int] = None,
    persist: bool = False,
) -> PatternRunResult:
    """Functional entry point for routes and Celery tasks."""
    return PatternEngine(db).detect(
        user_id,
        game_limit=game_limit,
        persist=persist,
    )
