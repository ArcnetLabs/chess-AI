"""Tests for deterministic chess-event detection.

The contract these guard: an event is derived only from stored move facts plus
the game result, carries the numbers behind its classification, and never
requires an engine call or an LLM at detection time.
"""

import chess
import pytest

from pathlib import Path

from app.models.game_move import GameMove
from app.services.events import detect_events_for_game
from app.services.events.event_types import (
    EVENT_CONVERSION_FAILURE,
    EVENT_ENDGAME_TECHNIQUE_FAILURE,
    EVENT_FAILED_TO_PUNISH,
    EVENT_MAJOR_BLUNDER,
    EVENT_MISSED_WIN,
    EVENT_OPENING_DEVIATION,
    EVENT_TACTICAL_MISS,
    EVENT_THREAT_UNANSWERED,
    EVENT_TYPES,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    concept_for,
    severity_for_cp_loss,
)

START_FEN = chess.STARTING_FEN
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def move_row(
    *,
    ply: int,
    color: str,
    is_user_move: bool,
    fen_before: str,
    fen_after: str,
    cp_loss: float = 0.0,
    eval_before: float = 0.0,
    eval_after: float = 0.0,
    classification: str = "good",
    phase: str = "middlegame",
    features=None,
    move_uci: str = "e2e4",
    best_move_uci: str = "e2e4",
) -> GameMove:
    """Unpersisted GameMove with only the fields detectors read."""
    return GameMove(
        id=ply,
        user_id=1,
        game_id=1,
        ply=ply,
        move_number=(ply + 1) // 2,
        color=color,
        is_user_move=is_user_move,
        fen_before=fen_before,
        fen_after=fen_after,
        position_key=f"key{ply}",
        cp_loss=cp_loss,
        eval_before_cp=eval_before,
        eval_after_cp=eval_after,
        classification=classification,
        phase=phase,
        features=features or {"material_balance": 0, "material_band": "level"},
        move_uci=move_uci,
        best_move_uci=best_move_uci,
        is_mate_score=False,
    )


def types_of(events):
    return [event["event_type"] for event in events]


class TestSeverityAndTaxonomy:
    def test_severity_bands_follow_cp_loss(self):
        assert severity_for_cp_loss(10) == SEVERITY_LOW
        assert severity_for_cp_loss(200) != SEVERITY_LOW
        assert severity_for_cp_loss(350) == SEVERITY_HIGH
        assert severity_for_cp_loss(900) == SEVERITY_CRITICAL

    def test_every_event_type_has_a_concept(self):
        for event_type in EVENT_TYPES:
            assert concept_for(event_type)


class TestMajorBlunder:
    def test_blunder_above_threshold_is_detected_with_evidence(self):
        moves = [
            move_row(
                ply=1,
                color="white",
                is_user_move=True,
                fen_before=START_FEN,
                fen_after=AFTER_E4,
            ),
            move_row(
                ply=2,
                color="black",
                is_user_move=False,
                fen_before=AFTER_E4,
                fen_after=AFTER_E4,
            ),
            move_row(
                ply=3,
                color="white",
                is_user_move=True,
                fen_before=AFTER_E4,
                fen_after=AFTER_E4,
                cp_loss=420.0,
                eval_before=0.0,
                eval_after=-420.0,
                classification="blunder",
            ),
        ]
        events = detect_events_for_game(moves, game_result="black", user_color="white")
        blunders = [e for e in events if e["event_type"] == EVENT_MAJOR_BLUNDER]

        assert len(blunders) == 1
        blunder = blunders[0]
        assert blunder["severity"] == SEVERITY_HIGH
        assert blunder["evidence"]["cp_loss"] == 420.0
        assert blunder["detector_version"] >= 1

    def test_small_loss_is_not_a_blunder(self):
        moves = [
            move_row(
                ply=1,
                color="white",
                is_user_move=True,
                fen_before=START_FEN,
                fen_after=AFTER_E4,
                cp_loss=40.0,
            )
        ]
        assert EVENT_MAJOR_BLUNDER not in types_of(
            detect_events_for_game(moves, game_result="draw", user_color="white")
        )

    def test_opponent_moves_never_produce_user_events(self):
        moves = [
            move_row(
                ply=1,
                color="white",
                is_user_move=False,
                fen_before=START_FEN,
                fen_after=AFTER_E4,
                cp_loss=500.0,
                classification="blunder",
            )
        ]
        assert detect_events_for_game(moves, game_result="white", user_color="black") == []


class TestContextualDetectors:
    def test_missed_tactic_requires_a_capturable_piece(self):
        """A loss with nothing hanging is not a missed tactic."""
        common = dict(
            ply=3,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=250.0,
            eval_before=100.0,
            eval_after=-150.0,
        )
        with_target = move_row(
            **common, features={"opponent_hanging": ["d5"], "material_balance": 0}
        )
        without_target = move_row(
            **common, features={"opponent_hanging": [], "material_balance": 0}
        )

        assert EVENT_TACTICAL_MISS in types_of(
            detect_events_for_game([with_target], game_result="draw", user_color="white")
        )
        assert EVENT_TACTICAL_MISS not in types_of(
            detect_events_for_game([without_target], game_result="draw", user_color="white")
        )

    def test_missed_win_needs_a_winning_eval_before_the_move(self):
        winning = move_row(
            ply=3,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=250.0,
            eval_before=350.0,
            eval_after=50.0,
        )
        equal = move_row(
            ply=3,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=250.0,
            eval_before=50.0,
            eval_after=-200.0,
        )
        assert EVENT_MISSED_WIN in types_of(
            detect_events_for_game([winning], game_result="draw", user_color="white")
        )
        assert EVENT_MISSED_WIN not in types_of(
            detect_events_for_game([equal], game_result="draw", user_color="white")
        )

    def test_conversion_failure_only_when_the_game_was_not_won(self):
        losing_out = move_row(
            ply=3,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=250.0,
            eval_before=350.0,
            eval_after=50.0,
        )
        won = detect_events_for_game([losing_out], game_result="white", user_color="white")
        lost = detect_events_for_game([losing_out], game_result="black", user_color="white")

        assert EVENT_CONVERSION_FAILURE not in types_of(won)
        assert EVENT_CONVERSION_FAILURE in types_of(lost)

    def test_endgame_technique_is_phase_specific(self):
        endgame_loss = move_row(
            ply=40,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=200.0,
            phase="endgame",
        )
        middlegame_loss = move_row(
            ply=20,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=200.0,
            phase="middlegame",
        )
        assert EVENT_ENDGAME_TECHNIQUE_FAILURE in types_of(
            detect_events_for_game([endgame_loss], game_result="draw", user_color="white")
        )
        assert EVENT_ENDGAME_TECHNIQUE_FAILURE not in types_of(
            detect_events_for_game([middlegame_loss], game_result="draw", user_color="white")
        )

    def test_opening_deviation_is_a_knowledge_signal(self):
        opening_loss = move_row(
            ply=5,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=180.0,
            phase="opening",
        )
        events = detect_events_for_game([opening_loss], game_result="draw", user_color="white")
        assert EVENT_OPENING_DEVIATION in types_of(events)

    def test_unanswered_threat_requires_an_endangered_piece(self):
        threatened = move_row(
            ply=7,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=200.0,
            features={"mover_hanging": ["c3"], "material_balance": -320},
        )
        safe = move_row(
            ply=7,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=200.0,
            features={"mover_hanging": [], "material_balance": 0},
        )
        assert EVENT_THREAT_UNANSWERED in types_of(
            detect_events_for_game([threatened], game_result="draw", user_color="white")
        )
        assert EVENT_THREAT_UNANSWERED not in types_of(
            detect_events_for_game([safe], game_result="draw", user_color="white")
        )

    def test_failed_to_punish_uses_the_opponents_previous_error(self):
        opponent_error = move_row(
            ply=2,
            color="black",
            is_user_move=False,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=300.0,
            classification="blunder",
        )
        weak_reply = move_row(
            ply=3,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=200.0,
        )
        events = detect_events_for_game(
            [opponent_error, weak_reply], game_result="draw", user_color="white"
        )
        punish = [e for e in events if e["event_type"] == EVENT_FAILED_TO_PUNISH]
        assert len(punish) == 1
        # The opponent's move is recorded as the trigger — this is what makes
        # "you struggle when opponents do X" queryable.
        assert punish[0]["opponent_move"] == opponent_error.move_uci
        assert punish[0]["opponent_trigger_ply"] == 2
        assert punish[0]["evidence"]["opponent_cp_loss"] == 300.0

    def test_opponent_error_alone_is_not_a_user_event(self):
        opponent_error = move_row(
            ply=2,
            color="black",
            is_user_move=False,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=300.0,
        )
        assert detect_events_for_game(
            [opponent_error], game_result="draw", user_color="white"
        ) == []


class TestImportOrder:
    """The events package must be importable before the analysis package.

    A module-scope import of ``move_facts`` from the detector closed a cycle
    (``analysis`` → ``events`` → ``analysis``) and broke every entry point that
    imports the events package first — production's path. The rest of the suite
    imports in the other order, so it stayed green while the real entry point failed.
    """

    def test_events_package_imports_before_analysis(self):
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import app.services.events; import app.services.analysis; print('ok')",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        assert "ok" in result.stdout, result.stderr[-2000:]


class TestMateRows:
    """Mate rows are gated on a *verified* reversal, not on the analyzer's label.

    The convention was checked against the games themselves: across 711 mate rows the
    mating side it implies matched the eventual winner in 97 of 98 finished games. The
    analyzer's classification, meanwhile, flattens mate to 0 cp and calls 602 of those
    711 rows "best" — including both rows where a forced mate was thrown away. Gating
    on that label admitted rows on a signal that cannot see mate and excluded the
    clearest blunders in the library.
    """

    def _mate_move(self, *, before: float, after: float, classification: str = "best"):
        row = move_row(
            ply=40,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=max(0.0, before - after),
            eval_before=before,
            eval_after=after,
            classification=classification,
            phase="endgame",
        )
        row.is_mate_score = True
        return row

    def test_throwing_away_a_forced_mate_produces_an_event(self):
        """The case the old gate excluded: mate in hand, then losing — labelled best."""
        row = self._mate_move(before=1200.0, after=-1200.0, classification="best")
        events = detect_events_for_game([row], game_result="black", user_color="white")
        assert EVENT_MAJOR_BLUNDER in types_of(events), types_of(events)

    def test_getting_mated_produces_an_event(self):
        row = self._mate_move(before=-200.0, after=-1200.0, classification="best")
        assert EVENT_MAJOR_BLUNDER in types_of(
            detect_events_for_game([row], game_result="black", user_color="white")
        )

    def test_a_slower_mate_is_not_a_blunder(self):
        """Still mating after the move: converting more slowly is not an error."""
        row = self._mate_move(before=1200.0, after=1200.0, classification="best")
        assert detect_events_for_game([row], game_result="white", user_color="white") == []

    def test_a_still_lost_position_is_not_an_event(self):
        """Being mated before and after says nothing about *this* move."""
        row = self._mate_move(before=-1200.0, after=-1200.0, classification="best")
        assert detect_events_for_game([row], game_result="black", user_color="white") == []

    def test_non_mate_rows_are_unaffected(self):
        row = move_row(
            ply=20,
            color="white",
            is_user_move=True,
            fen_before=AFTER_E4,
            fen_after=AFTER_E4,
            cp_loss=350.0,
            classification="good",
        )
        assert row.is_mate_score is False
        assert EVENT_MAJOR_BLUNDER in types_of(
            detect_events_for_game([row], game_result="draw", user_color="white")
        )


class TestDeterminism:
    def test_detection_is_repeatable(self):
        moves = [
            move_row(
                ply=1,
                color="white",
                is_user_move=True,
                fen_before=START_FEN,
                fen_after=AFTER_E4,
            ),
            move_row(
                ply=2,
                color="black",
                is_user_move=False,
                fen_before=AFTER_E4,
                fen_after=AFTER_E4,
            ),
            move_row(
                ply=3,
                color="white",
                is_user_move=True,
                fen_before=AFTER_E4,
                fen_after=AFTER_E4,
                cp_loss=400.0,
                eval_before=0.0,
                eval_after=-400.0,
                classification="blunder",
                phase="endgame",
            ),
        ]
        first = detect_events_for_game(moves, game_result="black", user_color="white")
        second = detect_events_for_game(moves, game_result="black", user_color="white")
        assert [e["event_type"] for e in first] == [e["event_type"] for e in second]
        assert all(e["evidence"] for e in first)
