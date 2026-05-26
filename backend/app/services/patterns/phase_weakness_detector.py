"""Phase weakness detection from Stockfish-derived ACPL aggregates."""

from __future__ import annotations

from typing import List, Optional

from .constants import (
    ENDGAME_ACPL_THRESHOLD,
    MIDDLEGAME_ACPL_THRESHOLD,
    MIN_PHASE_SAMPLE_GAMES,
    OPENING_ACPL_THRESHOLD,
    PATTERN_TYPE_PHASE,
    SEVERITY_CRITICAL_RATIO,
    SEVERITY_HIGH_RATIO,
)
from .types import DetectedPattern, PatternAggregationInput, PatternOccurrenceInput, PatternSeverity


def _severity_for_acpl(acpl: float, threshold: float) -> PatternSeverity:
    ratio = acpl / threshold if threshold > 0 else 0.0
    if ratio >= SEVERITY_CRITICAL_RATIO:
        return PatternSeverity.CRITICAL
    if ratio >= SEVERITY_HIGH_RATIO:
        return PatternSeverity.HIGH
    if ratio >= 1.0:
        return PatternSeverity.MEDIUM
    return PatternSeverity.LOW


def _confidence_score(acpl: float, threshold: float, games_count: int, total_games: int) -> float:
    """Deterministic 0–1 confidence from ACPL excess and sample size."""
    acpl_component = min(1.0, max(0.0, (acpl - threshold) / max(threshold, 1.0)))
    sample_component = min(1.0, games_count / max(MIN_PHASE_SAMPLE_GAMES, 1))
    coverage = games_count / max(total_games, 1)
    return round(min(1.0, 0.5 * acpl_component + 0.3 * sample_component + 0.2 * coverage), 4)


def _build_phase_pattern(
    *,
    phase: str,
    acpl: float,
    threshold: float,
    games_count: int,
    total_games: int,
    acpl_values: List[float],
    opening_by_game: List[dict],
) -> DetectedPattern:
    severity = _severity_for_acpl(acpl, threshold)
    confidence = _confidence_score(acpl, threshold, games_count, total_games)
    subtype = f"high_{phase}_acpl"

    # Games where this phase ACPL exceeded threshold (game-level occurrences).
    occurrences: List[PatternOccurrenceInput] = []
    example_positions: List[dict] = []

    for row in opening_by_game:
        game_id = row["game_id"]
        phase_acpl = row.get(f"{phase}_acpl")
        if phase_acpl is None:
            continue
        if phase_acpl <= threshold:
            continue
        occurrences.append(
            PatternOccurrenceInput(
                game_id=game_id,
                move_number=0,
                game_phase=phase,
                context_description=(
                    f"{phase.capitalize()} ACPL {phase_acpl:.1f} exceeds threshold {threshold:.1f}"
                ),
                detector_metadata={
                    "phase_acpl": phase_acpl,
                    "threshold": threshold,
                    "opening_name": row.get("opening_name"),
                },
            )
        )
        if len(example_positions) < 5:
            example_positions.append(
                {
                    "game_id": game_id,
                    "phase": phase,
                    "acpl": phase_acpl,
                    "opening_name": row.get("opening_name"),
                }
            )

    # Fallback: attach games from aggregate list when per-game map unavailable.
    if not occurrences and acpl_values:
        for idx, value in enumerate(acpl_values):
            if value <= threshold:
                continue
            occurrences.append(
                PatternOccurrenceInput(
                    game_id=-(idx + 1),
                    move_number=0,
                    game_phase=phase,
                    context_description=f"{phase.capitalize()} ACPL {value:.1f} in aggregate sample",
                    detector_metadata={"phase_acpl": value, "threshold": threshold},
                )
            )

    affected = len([o for o in occurrences if o.game_id > 0]) or games_count
    ratio = min(1.0, affected / max(total_games, 1))

    descriptions = {
        "opening": (
            f"Opening-phase ACPL averages {acpl:.1f} across {games_count} games "
            f"(threshold {threshold:.1f}). Recurring inaccuracies in the first phase "
            f"suggest preparation or opening-principle gaps."
        ),
        "middlegame": (
            f"Middlegame ACPL averages {acpl:.1f} across {games_count} games "
            f"(threshold {threshold:.1f}). Complex middlegame positions show "
            f"recurring calculation or planning errors."
        ),
        "endgame": (
            f"Endgame ACPL averages {acpl:.1f} across {games_count} games "
            f"(threshold {threshold:.1f}). Technique in simplified positions "
            f"needs structured study."
        ),
    }

    drill_map = {
        "opening": "opening_repertoire",
        "middlegame": "middlegame_calculation",
        "endgame": "endgame_technique",
    }

    return DetectedPattern(
        pattern_type=PATTERN_TYPE_PHASE,
        pattern_subtype=subtype,
        severity=severity,
        confidence_score=confidence,
        occurrence_count=max(affected, games_count),
        affected_games_count=affected,
        affected_games_ratio=round(ratio, 4),
        pattern_description=descriptions[phase],
        example_positions=example_positions,
        occurrences=[o for o in occurrences if o.game_id > 0],
        recommended_drill_type=drill_map.get(phase),
        evidence={
            "phase": phase,
            "average_acpl": round(acpl, 2),
            "threshold": threshold,
            "games_count": games_count,
            "detector": "phase_weakness_detector",
        },
    )


def detect_phase_weaknesses(data: PatternAggregationInput) -> List[DetectedPattern]:
    """
    Detect opening/middlegame/endgame weakness patterns from phase ACPL.

    Rules are deterministic thresholds on Stockfish-derived ``GameAnalysis`` fields.
    """
    patterns: List[DetectedPattern] = []
    total = data.total_analyzed_games

    phase_specs = [
        ("opening", data.opening_acpls, OPENING_ACPL_THRESHOLD),
        ("middlegame", data.middlegame_acpls, MIDDLEGAME_ACPL_THRESHOLD),
        ("endgame", data.endgame_acpls, ENDGAME_ACPL_THRESHOLD),
    ]

    # Enrich per-game rows with phase ACPL for occurrence linking.
    game_rows: List[dict] = []
    for row in data.opening_by_game:
        game_rows.append(dict(row))

    for phase, acpls, threshold in phase_specs:
        if len(acpls) < MIN_PHASE_SAMPLE_GAMES:
            continue
        average = sum(acpls) / len(acpls)
        if average <= threshold:
            continue

        patterns.append(
            _build_phase_pattern(
                phase=phase,
                acpl=average,
                threshold=threshold,
                games_count=len(acpls),
                total_games=total,
                acpl_values=acpls,
                opening_by_game=game_rows,
            )
        )

    return patterns
