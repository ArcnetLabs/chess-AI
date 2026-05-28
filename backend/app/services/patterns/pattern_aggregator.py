"""Aggregate detector outputs into a single pattern snapshot."""

from __future__ import annotations

from typing import List

from .blunder_cluster_detector import detect_blunder_clusters
from .opening_weakness_detector import detect_opening_weaknesses
from .phase_weakness_detector import detect_phase_weaknesses
from .types import DetectedPattern, PatternAggregationInput, PatternRunResult


class PatternAggregator:
    """Runs all MVP detectors and merges their outputs."""

    def aggregate(self, data: PatternAggregationInput) -> List[DetectedPattern]:
        patterns: List[DetectedPattern] = []
        patterns.extend(detect_phase_weaknesses(data))
        patterns.extend(detect_opening_weaknesses(data))
        patterns.extend(detect_blunder_clusters(data))
        return self._dedupe_by_key(patterns)

    @staticmethod
    def _dedupe_by_key(patterns: List[DetectedPattern]) -> List[DetectedPattern]:
        seen: set[tuple[str, str]] = set()
        unique: List[DetectedPattern] = []
        for pattern in patterns:
            key = pattern.pattern_key()
            if key in seen:
                continue
            seen.add(key)
            unique.append(pattern)
        return unique


def build_pattern_run_result(data: PatternAggregationInput) -> PatternRunResult:
    """Run aggregation pipeline and return an in-memory snapshot."""
    aggregator = PatternAggregator()
    patterns = aggregator.aggregate(data)
    return PatternRunResult(
        user_id=data.user_id,
        patterns=patterns,
        games_considered=data.total_analyzed_games,
    )
