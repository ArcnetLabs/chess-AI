"""Pattern recognition orchestrator (P1-PR-01).

Coordinates data loading, deterministic detection, and optional persistence.
Does not call Stockfish or any LLM — reads only persisted analysis truth.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from .pattern_aggregator import build_pattern_run_result
from .pattern_data import load_pattern_aggregation_input
from .pattern_service import persist_pattern_snapshots
from .types import PatternRunResult


class PatternEngine:
    """
    Orchestrates the pattern aggregation pipeline.

    Future detectors (blunder clusters, P1-PR-03+) register via ``PatternAggregator``.
    Celery tasks should call ``run_pattern_detection`` — not inline logic.
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
        logger.info(
            f"Pattern detection user_id={user_id}: "
            f"{result.pattern_count} patterns from {result.games_considered} games"
        )

        if persist and result.patterns:
            persist_pattern_snapshots(self._db, user_id, result)

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
