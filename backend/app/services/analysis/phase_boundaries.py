"""Canonical game-phase boundary calculation shared across services.

Single source of truth for where a game splits into opening, middlegame, and
endgame. Previously duplicated in ``UnifiedChessAnalyzer._analyze_phases``,
``game_detail_service._phase_boundaries``, and
``blunder_cluster_detector.infer_game_phase``.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

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


def phase_for_position(ply: int, total_plies: int, features: Optional[Dict] = None) -> str:
    """Phase of a position: the opening by move count, the endgame by material.

    The opening is genuinely about how many moves have been played — it is theory, and
    material tells you nothing about whether you are still in it. Everything after that
    is decided by what is on the board, not by how far into the game the players are.

    Measured before adopting: the move-number rule alone relabelled **27% of a real
    player's 8,599 rows**. 1,905 of those were positions with queens on and material
    not simplified being called endgames, and 424 were genuinely simplified positions —
    mass trades on move 20, or a queen ending — being called middlegames. Both
    directions matter for coaching, because the phase is part of a pattern's identity:
    an "endgame technique error" that happened in a queenless middlegame is a mislabel.

    ``simplified`` is the existing material notion (both sides at or below
    ``ENDGAME_MATERIAL_THRESHOLD`` non-pawn material), so a queen ending qualifies —
    which is correct: KQ vs KQ is an endgame.
    """
    move_phase = phase_for_move(ply, total_plies)
    if move_phase == "opening":
        return "opening"
    if features and features.get("simplified"):
        return "endgame"
    return "middlegame"