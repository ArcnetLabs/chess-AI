"""Canonical game-phase boundary calculation shared across services.

Single source of truth for where a game splits into opening, middlegame, and
endgame. Previously duplicated in ``UnifiedChessAnalyzer._analyze_phases``,
``game_detail_service._phase_boundaries``, and
``blunder_cluster_detector.infer_game_phase``.
"""

from __future__ import annotations

from typing import Dict, Tuple

OPENING_END_DIVISOR = 3
OPENING_MAX_MOVES = 20
ENDGAME_MIN_GAP = 10

PhaseRange = Tuple[int, int]

PHASE_NAMES = ("opening", "middlegame", "endgame")


def phase_boundaries(total_moves: int) -> Dict[str, PhaseRange]:
    """Return inclusive-start / exclusive-end move ranges per phase.

    Boundaries follow the original analyzer formula (opening ends at
    ``min(20, total // 3)``) with defensive clamps so very short games never
    produce degenerate or overlapping ranges.
    """
    raw_opening = total_moves // OPENING_END_DIVISOR if total_moves else 0
    opening_end = min(OPENING_MAX_MOVES, max(2, raw_opening or 2))
    endgame_start = max(opening_end + ENDGAME_MIN_GAP, (total_moves * 2) // OPENING_END_DIVISOR)
    if endgame_start <= opening_end:
        endgame_start = opening_end + 1

    return {
        "opening": (1, opening_end),
        "middlegame": (opening_end, endgame_start),
        "endgame": (endgame_start, total_moves + 1),
    }


def phase_for_move(move_number: int, total_moves: int) -> str:
    """Return the phase name containing ``move_number``."""
    for phase, (start, end) in phase_boundaries(total_moves).items():
        if start <= move_number < end:
            return phase
    return "endgame"