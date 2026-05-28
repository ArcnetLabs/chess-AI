"""Recurring opening weakness detection from per-game opening ACPL."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .constants import (
    MIN_OPENING_SAMPLE_GAMES,
    OPENING_SPECIFIC_ACPL_THRESHOLD,
    PATTERN_TYPE_OPENING,
    SEVERITY_CRITICAL_RATIO,
    SEVERITY_HIGH_RATIO,
)
from .types import DetectedPattern, PatternAggregationInput, PatternOccurrenceInput, PatternSeverity


def _slugify_opening(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "_")
        .replace(":", "")
        .replace("/", "_")[:64]
    )


def _severity_for_opening(acpl: float) -> PatternSeverity:
    ratio = acpl / OPENING_SPECIFIC_ACPL_THRESHOLD
    if ratio >= SEVERITY_CRITICAL_RATIO:
        return PatternSeverity.CRITICAL
    if ratio >= SEVERITY_HIGH_RATIO:
        return PatternSeverity.HIGH
    if ratio >= 1.0:
        return PatternSeverity.MEDIUM
    return PatternSeverity.LOW


def detect_opening_weaknesses(data: PatternAggregationInput) -> List[DetectedPattern]:
    """
    Detect recurring leaks in specific openings.

    Groups games by ``GameAnalysis.opening_name`` and flags openings where
    mean opening-phase ACPL exceeds ``OPENING_SPECIFIC_ACPL_THRESHOLD``.
    """
    by_opening: Dict[str, List[dict]] = defaultdict(list)
    for row in data.opening_by_game:
        name = row.get("opening_name")
        if not name or row.get("opening_acpl") is None:
            continue
        by_opening[name].append(row)

    patterns: List[DetectedPattern] = []
    total_games = data.total_analyzed_games

    for opening_name, games in by_opening.items():
        if len(games) < MIN_OPENING_SAMPLE_GAMES:
            continue

        acpls = [g["opening_acpl"] for g in games if g.get("opening_acpl") is not None]
        if not acpls:
            continue

        average_acpl = sum(acpls) / len(acpls)
        if average_acpl <= OPENING_SPECIFIC_ACPL_THRESHOLD:
            continue

        severity = _severity_for_opening(average_acpl)
        confidence = min(
            1.0,
            round(
                0.6 * min(1.0, (average_acpl - OPENING_SPECIFIC_ACPL_THRESHOLD) / 50.0)
                + 0.4 * min(1.0, len(games) / 5.0),
                4,
            ),
        )

        occurrences: List[PatternOccurrenceInput] = []
        example_positions: List[dict] = []

        for game in games:
            acpl = game.get("opening_acpl")
            if acpl is None or acpl <= OPENING_SPECIFIC_ACPL_THRESHOLD:
                continue
            occurrences.append(
                PatternOccurrenceInput(
                    game_id=game["game_id"],
                    move_number=0,
                    game_phase="opening",
                    context_description=(
                        f"Opening '{opening_name}' ACPL {acpl:.1f} "
                        f"(threshold {OPENING_SPECIFIC_ACPL_THRESHOLD:.1f})"
                    ),
                    detector_metadata={
                        "opening_name": opening_name,
                        "opening_eco": game.get("opening_eco"),
                        "opening_acpl": acpl,
                    },
                )
            )
            if len(example_positions) < 5:
                example_positions.append(
                    {
                        "game_id": game["game_id"],
                        "opening_name": opening_name,
                        "opening_eco": game.get("opening_eco"),
                        "opening_acpl": acpl,
                    }
                )

        affected = len(occurrences) or len(games)
        eco = games[0].get("opening_eco")
        subtype = _slugify_opening(opening_name)

        patterns.append(
            DetectedPattern(
                pattern_type=PATTERN_TYPE_OPENING,
                pattern_subtype=subtype,
                severity=severity,
                confidence_score=confidence,
                occurrence_count=affected,
                affected_games_count=affected,
                affected_games_ratio=round(
                    min(1.0, affected / max(total_games, 1)), 4
                ),
                pattern_description=(
                    f"Recurring weakness in {opening_name}"
                    f"{f' ({eco})' if eco else ''}: opening ACPL averages "
                    f"{average_acpl:.1f} over {len(games)} games "
                    f"(threshold {OPENING_SPECIFIC_ACPL_THRESHOLD:.1f})."
                ),
                example_positions=example_positions,
                occurrences=occurrences,
                recommended_drill_type="opening_repertoire",
                evidence={
                    "opening_name": opening_name,
                    "opening_eco": eco,
                    "average_opening_acpl": round(average_acpl, 2),
                    "games_count": len(games),
                    "threshold": OPENING_SPECIFIC_ACPL_THRESHOLD,
                    "detector": "opening_weakness_detector",
                },
            )
        )

    return patterns
