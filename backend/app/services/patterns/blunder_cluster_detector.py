"""Recurring blunder/mistake cluster detection from persisted move-level analysis."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .constants import (
    LEGACY_BLUNDER_RATE_THRESHOLD,
    MIN_BLUNDER_CLUSTER_GAMES,
    MIN_BLUNDER_CLUSTER_OCCURRENCES,
    MIN_LEGACY_BLUNDER_SAMPLE_GAMES,
    PATTERN_TYPE_BLUNDER,
    SEVERITY_CRITICAL_RATIO,
    SEVERITY_HIGH_RATIO,
    SWING_BAND_MAJOR_CP,
    SWING_BAND_MODERATE_CP,
)
from .types import DetectedPattern, PatternAggregationInput, PatternOccurrenceInput, PatternSeverity


def infer_game_phase(move_number: int, total_moves: int) -> str:
    """Mirror ``UnifiedChessAnalyzer._analyze_phases`` boundaries."""
    opening_end = min(20, total_moves // 3)
    endgame_start = max(opening_end + 10, total_moves * 2 // 3)
    if move_number < opening_end:
        return "opening"
    if move_number >= endgame_start:
        return "endgame"
    return "middlegame"


def _swing_band(classification: str, eval_delta: float) -> Optional[str]:
    """Map a blunder/mistake event to a deterministic eval-swing band."""
    if classification == "blunder" or eval_delta >= SWING_BAND_MAJOR_CP:
        return "major"
    if classification == "mistake" or eval_delta >= SWING_BAND_MODERATE_CP:
        return "moderate"
    return None


def _severity_for_cluster(occurrences: int, games: int, min_games: int) -> PatternSeverity:
    ratio = occurrences / max(min_games, 1)
    if ratio >= SEVERITY_CRITICAL_RATIO and games >= min_games + 1:
        return PatternSeverity.CRITICAL
    if ratio >= SEVERITY_HIGH_RATIO:
        return PatternSeverity.HIGH
    if occurrences >= min_games:
        return PatternSeverity.MEDIUM
    return PatternSeverity.LOW


def _confidence_for_cluster(
    occurrences: int,
    games: int,
    total_games: int,
    min_occurrences: int,
) -> float:
    occ_component = min(1.0, occurrences / max(min_occurrences, 1))
    game_component = min(1.0, games / max(MIN_BLUNDER_CLUSTER_GAMES, 1))
    coverage = games / max(total_games, 1)
    return round(min(1.0, 0.5 * occ_component + 0.3 * game_component + 0.2 * coverage), 4)


def _build_cluster_pattern(
    *,
    phase: str,
    band: str,
    events: List[dict],
    total_games: int,
) -> DetectedPattern:
    game_ids = {e["game_id"] for e in events}
    affected = len(game_ids)
    subtype = f"{phase}_{band}_swings"
    severity = _severity_for_cluster(len(events), affected, MIN_BLUNDER_CLUSTER_GAMES)
    confidence = _confidence_for_cluster(
        len(events), affected, total_games, MIN_BLUNDER_CLUSTER_OCCURRENCES
    )

    occurrences: List[PatternOccurrenceInput] = []
    example_positions: List[dict] = []

    for event in events:
        eval_delta = event.get("eval_delta", 0.0)
        occurrences.append(
            PatternOccurrenceInput(
                game_id=event["game_id"],
                move_number=event.get("move_number", 0),
                game_phase=phase,
                fen_before=event.get("fen_before"),
                fen_after=event.get("fen_after"),
                user_move=event.get("move_san"),
                best_move=event.get("best_move_uci"),
                eval_delta=eval_delta,
                context_description=(
                    f"{phase.capitalize()} {band} eval swing ({eval_delta:.0f} cp) "
                    f"on move {event.get('move_number', '?')}"
                ),
                detector_metadata={
                    "classification": event.get("classification"),
                    "swing_band": band,
                    "phase": phase,
                },
            )
        )
        if len(example_positions) < 5:
            example_positions.append(
                {
                    "game_id": event["game_id"],
                    "move_number": event.get("move_number"),
                    "fen_before": event.get("fen_before"),
                    "eval_delta": eval_delta,
                    "phase": phase,
                    "band": band,
                }
            )

    band_label = "major blunders" if band == "major" else "significant mistakes"
    return DetectedPattern(
        pattern_type=PATTERN_TYPE_BLUNDER,
        pattern_subtype=subtype,
        severity=severity,
        confidence_score=confidence,
        occurrence_count=len(events),
        affected_games_count=affected,
        affected_games_ratio=round(min(1.0, affected / max(total_games, 1)), 4),
        pattern_description=(
            f"Recurring {band_label} in the {phase} "
            f"({len(events)} events across {affected} games)."
        ),
        example_positions=example_positions,
        occurrences=occurrences,
        recommended_drill_type=f"{phase}_tactics",
        evidence={
            "phase": phase,
            "swing_band": band,
            "occurrence_count": len(events),
            "affected_games": affected,
            "detector": "blunder_cluster_detector",
        },
    )


def _detect_move_level_clusters(data: PatternAggregationInput) -> List[DetectedPattern]:
    clusters: Dict[Tuple[str, str], List[dict]] = defaultdict(list)

    for event in data.blunder_events:
        phase = event.get("game_phase") or infer_game_phase(
            event.get("move_number", 1),
            event.get("total_moves_estimate", 60),
        )
        eval_delta = abs(float(event.get("eval_delta") or event.get("evaluation_change") or 0))
        band = _swing_band(event.get("classification", ""), eval_delta)
        if band is None:
            continue
        clusters[(phase, band)].append({**event, "eval_delta": eval_delta})

    patterns: List[DetectedPattern] = []
    for (phase, band), events in sorted(clusters.items()):
        game_ids = {e["game_id"] for e in events}
        if len(events) < MIN_BLUNDER_CLUSTER_OCCURRENCES:
            continue
        if len(game_ids) < MIN_BLUNDER_CLUSTER_GAMES:
            continue
        patterns.append(
            _build_cluster_pattern(
                phase=phase,
                band=band,
                events=events,
                total_games=data.total_analyzed_games,
            )
        )
    return patterns


def _detect_legacy_high_blunder_rate(data: PatternAggregationInput) -> List[DetectedPattern]:
    """Aggregate blunder-rate pattern for legacy rows without move-level JSON."""
    stats = data.games_blunder_stats
    if len(stats) < MIN_LEGACY_BLUNDER_SAMPLE_GAMES:
        return []

    blunder_counts = [s.get("blunder_count", 0) or 0 for s in stats]
    avg_rate = sum(blunder_counts) / len(blunder_counts)
    if avg_rate < LEGACY_BLUNDER_RATE_THRESHOLD:
        return []

    high_blunder_games = [s for s in stats if (s.get("blunder_count") or 0) >= 1]
    affected = len(high_blunder_games)
    severity = _severity_for_cluster(
        sum(blunder_counts), affected, MIN_LEGACY_BLUNDER_SAMPLE_GAMES
    )
    confidence = min(
        1.0,
        round(
            0.6 * min(1.0, (avg_rate - LEGACY_BLUNDER_RATE_THRESHOLD) / 2.0)
            + 0.4 * min(1.0, len(stats) / 5.0),
            4,
        ),
    )

    occurrences: List[PatternOccurrenceInput] = []
    for row in high_blunder_games:
        count = row.get("blunder_count") or 0
        occurrences.append(
            PatternOccurrenceInput(
                game_id=row["game_id"],
                move_number=0,
                context_description=f"{count} blunder(s) in game (legacy aggregate)",
                detector_metadata={"blunder_count": count, "legacy": True},
            )
        )

    return [
        DetectedPattern(
            pattern_type=PATTERN_TYPE_BLUNDER,
            pattern_subtype="high_blunder_rate",
            severity=severity,
            confidence_score=confidence,
            occurrence_count=sum(blunder_counts),
            affected_games_count=affected,
            affected_games_ratio=round(
                min(1.0, affected / max(data.total_analyzed_games, 1)), 4
            ),
            pattern_description=(
                f"High blunder rate: averages {avg_rate:.1f} blunders per game "
                f"across {len(stats)} analyzed games "
                f"(threshold {LEGACY_BLUNDER_RATE_THRESHOLD:.1f})."
            ),
            occurrences=occurrences,
            recommended_drill_type="calculation_drills",
            evidence={
                "average_blunders_per_game": round(avg_rate, 2),
                "threshold": LEGACY_BLUNDER_RATE_THRESHOLD,
                "games_count": len(stats),
                "legacy_aggregate": True,
                "detector": "blunder_cluster_detector",
            },
        )
    ]


def detect_blunder_clusters(data: PatternAggregationInput) -> List[DetectedPattern]:
    """
    Detect recurring blunder themes from persisted ``GameAnalysis`` move JSON.

    Uses move-level ``blunder_moves`` when available; falls back to game-level
    blunder counts only when no move-level events exist in the sample.
    """
    if data.blunder_events:
        return _detect_move_level_clusters(data)
    return _detect_legacy_high_blunder_rate(data)
