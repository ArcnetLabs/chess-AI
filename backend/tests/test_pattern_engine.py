"""Tests for deterministic pattern recognition (P1-PR-01 / P1-PR-02)."""

from datetime import datetime, timezone

import pytest

from app.services.patterns.constants import (
    ENDGAME_ACPL_THRESHOLD,
    MIDDLEGAME_ACPL_THRESHOLD,
    MIN_OPENING_SAMPLE_GAMES,
    MIN_PHASE_SAMPLE_GAMES,
    OPENING_ACPL_THRESHOLD,
    OPENING_SPECIFIC_ACPL_THRESHOLD,
    PATTERN_TYPE_BLUNDER,
    PATTERN_TYPE_OPENING,
    PATTERN_TYPE_PHASE,
)
from app.services.patterns.opening_weakness_detector import detect_opening_weaknesses
from app.services.patterns.pattern_aggregator import build_pattern_run_result
from app.services.patterns.phase_weakness_detector import detect_phase_weaknesses
from app.services.patterns.types import PatternAggregationInput


def _base_input(**overrides) -> PatternAggregationInput:
    data = PatternAggregationInput(
        user_id=1,
        total_analyzed_games=5,
        opening_acpls=[25.0, 28.0, 26.0, 27.0, 24.0],
        middlegame_acpls=[30.0, 32.0, 31.0, 29.0, 30.0],
        endgame_acpls=[35.0, 36.0, 34.0, 33.0, 35.0],
        opening_by_game=[
            {
                "game_id": i + 1,
                "opening_name": "Sicilian Defense",
                "opening_eco": "B90",
                "opening_acpl": 52.0 + i,
                "middlegame_acpl": 30.0,
                "endgame_acpl": 35.0,
            }
            for i in range(5)
        ],
    )
    for key, value in overrides.items():
        setattr(data, key, value)
    return data


class TestPhaseWeaknessDetector:
    def test_no_pattern_below_threshold(self):
        patterns = detect_phase_weaknesses(_base_input())
        phase_patterns = [p for p in patterns if p.pattern_type == PATTERN_TYPE_PHASE]
        assert phase_patterns == []

    def test_opening_weakness_when_acpl_high(self):
        data = _base_input(
            opening_acpls=[40.0, 42.0, 38.0, 41.0],
            total_analyzed_games=4,
        )
        patterns = detect_phase_weaknesses(data)
        opening = [p for p in patterns if p.pattern_subtype == "high_opening_acpl"]
        assert len(opening) == 1
        assert opening[0].confidence_score > 0
        assert opening[0].evidence["average_acpl"] > OPENING_ACPL_THRESHOLD

    def test_requires_minimum_sample(self):
        data = _base_input(
            opening_acpls=[50.0, 55.0],
            total_analyzed_games=2,
        )
        assert detect_phase_weaknesses(data) == []

    def test_middlegame_and_endgame_patterns(self):
        data = _base_input(
            opening_acpls=[20.0, 22.0, 21.0],
            middlegame_acpls=[50.0, 48.0, 52.0],
            endgame_acpls=[55.0, 54.0, 56.0],
            total_analyzed_games=3,
        )
        patterns = detect_phase_weaknesses(data)
        subtypes = {p.pattern_subtype for p in patterns}
        assert "high_middlegame_acpl" in subtypes
        assert "high_endgame_acpl" in subtypes
        assert "high_opening_acpl" not in subtypes


class TestOpeningWeaknessDetector:
    def test_recurring_opening_leak(self):
        data = _base_input()
        patterns = detect_opening_weaknesses(data)
        assert len(patterns) == 1
        assert patterns[0].pattern_type == PATTERN_TYPE_OPENING
        assert "Sicilian" in patterns[0].pattern_description
        assert patterns[0].affected_games_count >= MIN_OPENING_SAMPLE_GAMES
        assert patterns[0].evidence["average_opening_acpl"] > OPENING_SPECIFIC_ACPL_THRESHOLD

    def test_insufficient_opening_sample(self):
        data = _base_input(
            opening_by_game=[
                {
                    "game_id": 1,
                    "opening_name": "French Defense",
                    "opening_eco": "C00",
                    "opening_acpl": 60.0,
                    "middlegame_acpl": 30.0,
                    "endgame_acpl": 35.0,
                }
            ],
            total_analyzed_games=1,
        )
        assert detect_opening_weaknesses(data) == []

    def test_multiple_openings_only_flags_weak_line(self):
        data = _base_input(
            opening_by_game=[
                {
                    "game_id": 1,
                    "opening_name": "Italian Game",
                    "opening_eco": "C50",
                    "opening_acpl": 20.0,
                    "middlegame_acpl": 30.0,
                    "endgame_acpl": 35.0,
                },
                {
                    "game_id": 2,
                    "opening_name": "Italian Game",
                    "opening_eco": "C50",
                    "opening_acpl": 22.0,
                    "middlegame_acpl": 30.0,
                    "endgame_acpl": 35.0,
                },
                {
                    "game_id": 3,
                    "opening_name": "King's Indian",
                    "opening_eco": "E60",
                    "opening_acpl": 55.0,
                    "middlegame_acpl": 30.0,
                    "endgame_acpl": 35.0,
                },
                {
                    "game_id": 4,
                    "opening_name": "King's Indian",
                    "opening_eco": "E60",
                    "opening_acpl": 58.0,
                    "middlegame_acpl": 30.0,
                    "endgame_acpl": 35.0,
                },
            ],
            total_analyzed_games=4,
        )
        patterns = detect_opening_weaknesses(data)
        assert len(patterns) == 1
        assert "King's Indian" in patterns[0].pattern_description


class TestPatternAggregator:
    def test_build_run_result_combines_detectors(self):
        data = _base_input(
            opening_acpls=[40.0, 41.0, 39.0, 42.0, 40.0],
            total_analyzed_games=5,
        )
        result = build_pattern_run_result(data)
        assert result.user_id == 1
        assert result.games_considered == 5
        types = {p.pattern_type for p in result.patterns}
        assert PATTERN_TYPE_PHASE in types
        assert PATTERN_TYPE_OPENING in types
        keys = {p.pattern_key() for p in result.patterns}
        assert len(keys) == len(result.patterns)

    def test_blunder_cluster_in_aggregator_with_move_events(self):
        events = [
            {
                "game_id": gid,
                "move_number": 30,
                "move_san": "Qh4??",
                "fen_before": "start",
                "classification": "blunder",
                "eval_delta": 400.0,
                "total_moves_estimate": 60,
                "game_phase": "middlegame",
            }
            for gid in range(1, 4)
        ]
        events.append(dict(events[0], move_number=32))
        data = _base_input(blunder_events=events)
        result = build_pattern_run_result(data)
        blunder = [p for p in result.patterns if p.pattern_type == PATTERN_TYPE_BLUNDER]
        assert len(blunder) >= 1
