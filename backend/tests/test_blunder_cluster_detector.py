"""Tests for blunder cluster detection (P1-PR-03)."""

from app.services.patterns.blunder_cluster_detector import (
    detect_blunder_clusters,
    infer_game_phase,
)
from app.services.patterns.constants import (
    LEGACY_BLUNDER_RATE_THRESHOLD,
    MIN_BLUNDER_CLUSTER_GAMES,
    MIN_BLUNDER_CLUSTER_OCCURRENCES,
    PATTERN_TYPE_BLUNDER,
)
from app.services.patterns.pattern_aggregator import build_pattern_run_result
from app.services.patterns.types import PatternAggregationInput


def _event(
    game_id: int,
    move_number: int,
    *,
    classification: str = "blunder",
    eval_delta: float = 350.0,
    phase: str | None = None,
) -> dict:
    return {
        "game_id": game_id,
        "move_number": move_number,
        "move_san": "Qh4??",
        "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "fen_after": "rnbqkbnr/pppppppp/8/8/8/7Q/PPPPPPPP/RNBQKBNR b KQkq - 1 1",
        "best_move_uci": "e2e4",
        "classification": classification,
        "eval_delta": eval_delta,
        "total_moves_estimate": 60,
        "game_phase": phase,
    }


def _base_input(**overrides) -> PatternAggregationInput:
    data = PatternAggregationInput(
        user_id=1,
        total_analyzed_games=5,
        opening_acpls=[25.0] * 5,
        middlegame_acpls=[30.0] * 5,
        endgame_acpls=[35.0] * 5,
        opening_by_game=[],
        blunder_events=[],
        games_blunder_stats=[
            {"game_id": i + 1, "blunder_count": 0, "mistake_count": 0} for i in range(5)
        ],
    )
    for key, value in overrides.items():
        setattr(data, key, value)
    return data


class TestInferGamePhase:
    def test_opening_middlegame_endgame_boundaries(self):
        total = 60
        assert infer_game_phase(5, total) == "opening"
        assert infer_game_phase(30, total) == "middlegame"
        assert infer_game_phase(50, total) == "endgame"


class TestMoveLevelClusters:
    def test_no_pattern_below_thresholds(self):
        events = [_event(1, 10), _event(1, 20)]
        patterns = detect_blunder_clusters(_base_input(blunder_events=events))
        assert patterns == []

    def test_middlegame_major_cluster(self):
        events = [
            _event(gid, 30, phase="middlegame")
            for gid in range(1, MIN_BLUNDER_CLUSTER_GAMES + 1)
        ]
        events.append(_event(1, 32, phase="middlegame"))
        patterns = detect_blunder_clusters(
            _base_input(
                blunder_events=events,
                total_analyzed_games=MIN_BLUNDER_CLUSTER_GAMES + 1,
            )
        )
        assert len(patterns) == 1
        pattern = patterns[0]
        assert pattern.pattern_type == PATTERN_TYPE_BLUNDER
        assert pattern.pattern_subtype == "middlegame_major_swings"
        assert pattern.occurrence_count >= MIN_BLUNDER_CLUSTER_OCCURRENCES
        assert pattern.affected_games_count >= MIN_BLUNDER_CLUSTER_GAMES
        assert all(o.game_id > 0 for o in pattern.occurrences)
        assert all(o.eval_delta is not None for o in pattern.occurrences)
        assert pattern.example_positions[0]["fen_before"]

    def test_moderate_mistake_band(self):
        events = [
            _event(gid, 25, classification="mistake", eval_delta=220.0, phase="middlegame")
            for gid in range(1, 4)
        ]
        patterns = detect_blunder_clusters(_base_input(blunder_events=events))
        assert len(patterns) == 1
        assert patterns[0].pattern_subtype == "middlegame_moderate_swings"

    def test_inferred_phase_when_not_provided(self):
        events = [
            _event(gid, 30, eval_delta=400.0)
            for gid in range(1, 4)
        ]
        events.append(_event(1, 32, eval_delta=400.0))
        patterns = detect_blunder_clusters(_base_input(blunder_events=events))
        assert any(p.pattern_subtype.startswith("middlegame_") for p in patterns)


class TestLegacyHighBlunderRate:
    def test_legacy_pattern_when_no_move_json(self):
        stats = [
            {"game_id": 1, "blunder_count": 2, "mistake_count": 1},
            {"game_id": 2, "blunder_count": 2, "mistake_count": 0},
            {"game_id": 3, "blunder_count": 1, "mistake_count": 2},
        ]
        patterns = detect_blunder_clusters(
            _base_input(
                blunder_events=[],
                games_blunder_stats=stats,
                total_analyzed_games=3,
            )
        )
        assert len(patterns) == 1
        assert patterns[0].pattern_subtype == "high_blunder_rate"
        assert patterns[0].evidence["legacy_aggregate"] is True
        avg = patterns[0].evidence["average_blunders_per_game"]
        assert avg >= LEGACY_BLUNDER_RATE_THRESHOLD

    def test_no_legacy_pattern_when_move_json_present(self):
        stats = [
            {"game_id": i + 1, "blunder_count": 3, "mistake_count": 0}
            for i in range(3)
        ]
        patterns = detect_blunder_clusters(
            _base_input(
                blunder_events=[_event(1, 10)],
                games_blunder_stats=stats,
            )
        )
        subtypes = {p.pattern_subtype for p in patterns}
        assert "high_blunder_rate" not in subtypes

    def test_legacy_below_threshold(self):
        stats = [
            {"game_id": 1, "blunder_count": 1, "mistake_count": 0},
            {"game_id": 2, "blunder_count": 0, "mistake_count": 1},
            {"game_id": 3, "blunder_count": 1, "mistake_count": 0},
        ]
        assert detect_blunder_clusters(
            _base_input(blunder_events=[], games_blunder_stats=stats)
        ) == []


class TestAggregatorIntegration:
    def test_build_run_result_includes_blunder_patterns(self):
        events = [
            _event(gid, 30, phase="middlegame")
            for gid in range(1, 4)
        ]
        events.append(_event(1, 32, phase="middlegame"))
        result = build_pattern_run_result(_base_input(blunder_events=events))
        types = {p.pattern_type for p in result.patterns}
        assert PATTERN_TYPE_BLUNDER in types
