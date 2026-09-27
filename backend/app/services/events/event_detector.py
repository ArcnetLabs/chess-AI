"""Deterministic chess-event detection over stored move facts.

Each detector reads only persisted ``game_moves`` rows (plus the game result),
so an event can always be re-derived from the database. No engine call, no LLM.

Detectors are intentionally conservative and independent: one move can produce
more than one event (a blunder that is also a missed tactic), and that is
desirable — the pattern layer decides which co-occurrences matter.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from app.models.game_move import GameMove

from .event_types import (
    BLUNDER_CP_LOSS,
    CLEAR_ADVANTAGE,
    EVENT_CONVERSION_FAILURE,
    EVENT_ENDGAME_TECHNIQUE_FAILURE,
    EVENT_EXCHANGE_ERROR,
    EVENT_FAILED_TO_PUNISH,
    EVENT_KING_SAFETY_ERROR,
    EVENT_MAJOR_BLUNDER,
    EVENT_MISSED_WIN,
    EVENT_OPENING_DEVIATION,
    EVENT_PAWN_STRUCTURE_WEAKENING,
    EVENT_PIECE_ACTIVITY_ERROR,
    EVENT_STRUCTURE_ERROR,
    EVENT_TACTICAL_MISS,
    EVENT_THREAT_UNANSWERED,
    EVENT_DETECTOR_VERSION,
    OPPONENT_ERROR_CP_LOSS,
    SIGNIFICANT_CP_LOSS,
    WINNING_EVAL,
    concept_for,
    severity_for_cp_loss,
)

# A phase's context matters: an eval drop in the endgame is a technique problem,
# the same drop in the opening is usually knowledge.
_ENDGAME = "endgame"
_OPENING = "opening"
_MIDDLEGAME = "middlegame"


def _event(
    *,
    move: GameMove,
    event_type: str,
    cp_loss: float,
    evidence: Dict,
    opponent_move: Optional[str] = None,
    opponent_trigger_ply: Optional[int] = None,
) -> Dict:
    """Build one event row dict with its evidence payload."""
    return {
        "user_id": move.user_id,
        "game_id": move.game_id,
        "move_id": move.id,
        "event_type": event_type,
        "concept": concept_for(event_type),
        "severity": severity_for_cp_loss(cp_loss),
        "phase": move.phase or _MIDDLEGAME,
        "move_number": move.move_number,
        "position_key": move.position_key,
        "fen_before": move.fen_before,
        "played_move": move.move_uci,
        "best_move": move.best_move_uci,
        "eval_before_cp": move.eval_before_cp,
        "cp_loss": move.cp_loss,
        "opponent_trigger_ply": opponent_trigger_ply,
        "opponent_move": opponent_move,
        "evidence": evidence,
        "detector_id": event_type,
        "detector_version": EVENT_DETECTOR_VERSION,
    }


def _was_capture(move: GameMove) -> bool:
    """True when the played move captured something.

    Derived from the two FENs rather than stored, so it holds for backfilled
    rows too: a capture removes exactly one enemy piece.
    """
    import chess

    try:
        before = chess.Board(move.fen_before)
        after = chess.Board(move.fen_after)
    except ValueError:
        return False

    mover = chess.WHITE if move.color == "white" else chess.BLACK
    before_count = len(before.piece_map())
    after_count = len(after.piece_map())
    # A capture reduces the total by one; anything else (promotion) is excluded
    # by requiring the mover's own material to be unchanged or higher.
    return before_count - after_count == 1 and before.turn == mover


def _features(move: GameMove) -> Dict:
    return move.features or {}


def detect_events_for_game(
    moves: Sequence[GameMove],
    *,
    game_result: Optional[str] = None,
    user_color: str = "white",
) -> List[Dict]:
    """All events for one game, derived from its move facts.

    ``game_result`` is the winner ("white"/"black"/"draw"/None) and is used only
    for conversion failures — every other detector is purely positional.
    """
    events: List[Dict] = []
    by_ply = {move.ply: move for move in moves}
    user_won = game_result == user_color

    for move in moves:
        if not move.is_user_move:
            continue

        cp_loss = float(move.cp_loss or 0.0)
        eval_before = float(move.eval_before_cp or 0.0)
        eval_after = float(move.eval_after_cp or 0.0)
        features = _features(move)
        opponent = by_ply.get(move.ply - 1)
        opponent_move = opponent.move_uci if opponent else None
        opponent_trigger_ply = None

        # Opponent's previous move was itself an error: worth remembering even
        # when the player's reply was fine, because "punishing mistakes" is a
        # distinct skill from "not making them".
        opponent_erred = bool(
            opponent
            and not opponent.is_user_move
            and float(opponent.cp_loss or 0.0) >= OPPONENT_ERROR_CP_LOSS
        )

        # 1. Major blunder — the blunt signal.
        if cp_loss >= BLUNDER_CP_LOSS:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_MAJOR_BLUNDER,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "eval_before": eval_before,
                        "eval_after": eval_after,
                        "classification": move.classification,
                        "phase": move.phase,
                    },
                    opponent_move=opponent_move,
                    opponent_trigger_ply=opponent.ply if opponent else None,
                )
            )

        # 2. Missed tactic — a significant drop while a capture was available.
        #    The available material is measured before the move, so this is
        #    "there was something to take and the move did not take it".
        opponent_hanging = features.get("opponent_hanging") or []
        if cp_loss >= SIGNIFICANT_CP_LOSS and opponent_hanging:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_TACTICAL_MISS,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "capturable_squares": opponent_hanging,
                        "best_move": move.best_move_uci,
                        "played_move": move.move_uci,
                    },
                    opponent_move=opponent_move,
                    opponent_trigger_ply=opponent.ply if opponent else None,
                )
            )

        # 3. Missed win — was clearly better, ended up not better.
        if eval_before >= WINNING_EVAL and eval_after < CLEAR_ADVANTAGE:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_MISSED_WIN,
                    cp_loss=cp_loss,
                    evidence={
                        "eval_before": eval_before,
                        "eval_after": eval_after,
                        "cp_loss": cp_loss,
                        "phase": move.phase,
                    },
                    opponent_move=opponent_move,
                    opponent_trigger_ply=opponent.ply if opponent else None,
                )
            )

        # 4. Conversion failure — reached a winning position and did not win it.
        if eval_before >= WINNING_EVAL and not user_won and cp_loss >= SIGNIFICANT_CP_LOSS:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_CONVERSION_FAILURE,
                    cp_loss=cp_loss,
                    evidence={
                        "eval_before": eval_before,
                        "game_result": game_result,
                        "cp_loss": cp_loss,
                        "material_band": features.get("material_band"),
                    },
                )
            )

        # 5. Endgame technique — a real drop once the position is simplified.
        if move.phase == _ENDGAME and cp_loss >= SIGNIFICANT_CP_LOSS:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_ENDGAME_TECHNIQUE_FAILURE,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "eval_before": eval_before,
                        "eval_after": eval_after,
                        "simplified": features.get("simplified"),
                        "material_band": features.get("material_band"),
                    },
                )
            )

        # 6. Opening deviation — a drop while still in the opening. Treated as a
        #    knowledge signal, not a tactical one.
        if move.phase == _OPENING and cp_loss >= SIGNIFICANT_CP_LOSS:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_OPENING_DEVIATION,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "move_number": move.move_number,
                        "played_move": move.move_uci,
                        "best_move": move.best_move_uci,
                    },
                )
            )

        # 7. Threat unanswered — the mover's own piece was hanging before the
        #    move and the move did not solve it.
        mover_hanging = features.get("mover_hanging") or []
        if mover_hanging and cp_loss >= SIGNIFICANT_CP_LOSS:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_THREAT_UNANSWERED,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "endangered_squares": mover_hanging,
                        "opponent_move": opponent_move,
                        "played_move": move.move_uci,
                    },
                    opponent_move=opponent_move,
                    opponent_trigger_ply=opponent.ply if opponent else None,
                )
            )

        # 8. Failed to punish — opponent erred and the player gained nothing.
        if opponent_erred and cp_loss >= SIGNIFICANT_CP_LOSS:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_FAILED_TO_PUNISH,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "opponent_cp_loss": opponent.cp_loss if opponent else None,
                        "opponent_move": opponent_move,
                        "played_move": move.move_uci,
                    },
                    opponent_move=opponent_move,
                    opponent_trigger_ply=opponent.ply if opponent else None,
                )
            )

        # 9. King safety — the opponent has more attackers around the king after
        #    a significant drop, with the king shield already reduced.
        if (
            cp_loss >= SIGNIFICANT_CP_LOSS
            and int(features.get("opponent_king_attackers") or 0) >= 3
            and int(features.get("mover_pawn_shield") or 0) <= 1
        ):
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_KING_SAFETY_ERROR,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "attackers": features.get("opponent_king_attackers"),
                        "pawn_shield": features.get("mover_pawn_shield"),
                        "mover_hanging": mover_hanging,
                    },
                    opponent_move=opponent_move,
                    opponent_trigger_ply=opponent.ply if opponent else None,
                )
            )

        # 10. Exchange error — a capture that lost material relative to the
        #     alternative (the position got worse for the mover by a real margin).
        if _was_capture(move) and cp_loss >= SIGNIFICANT_CP_LOSS:
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_EXCHANGE_ERROR,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "played_move": move.move_uci,
                        "best_move": move.best_move_uci,
                        "material_balance": features.get("material_balance"),
                    },
                )
            )

        # 11. Structure error — a significant drop where the mover's material is
        #     fine but the position keeps slipping in a non-simplified position.
        if (
            cp_loss >= SIGNIFICANT_CP_LOSS
            and not features.get("simplified")
            and move.phase != _OPENING
            and not mover_hanging
            and abs(int(features.get("material_balance") or 0)) < 100
        ):
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_STRUCTURE_ERROR,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "material_balance": features.get("material_balance"),
                        "queens_off": features.get("queens_off"),
                        "phase": move.phase,
                    },
                )
            )

        # 12. Piece activity — the mover's mobility collapsed alongside the eval.
        mobility = int(features.get("mobility") or 0)
        if (
            cp_loss >= SIGNIFICANT_CP_LOSS
            and mobility > 0
            and mobility <= 3
            and not mover_hanging
        ):
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_PIECE_ACTIVITY_ERROR,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "mobility": mobility,
                        "phase": move.phase,
                    },
                )
            )

        # 13. Premature pawn push — a slow pawn move that costs real evaluation
        #     while the opponent still has attacking pieces near the king.
        if (
            cp_loss >= SIGNIFICANT_CP_LOSS
            and _is_pawn_move(move)
            and not _was_capture(move)
            and int(features.get("opponent_king_attackers") or 0) >= 2
            and move.phase == _MIDDLEGAME
        ):
            events.append(
                _event(
                    move=move,
                    event_type=EVENT_PAWN_STRUCTURE_WEAKENING,
                    cp_loss=cp_loss,
                    evidence={
                        "cp_loss": cp_loss,
                        "played_move": move.move_uci,
                        "attackers": features.get("opponent_king_attackers"),
                        "pawn_shield": features.get("mover_pawn_shield"),
                    },
                    opponent_move=opponent_move,
                    opponent_trigger_ply=opponent.ply if opponent else None,
                )
            )

    return events


def _is_pawn_move(move: GameMove) -> bool:
    """True when the played move was a pawn move (no piece left its origin)."""
    import chess

    try:
        before = chess.Board(move.fen_before)
        after = chess.Board(move.fen_after)
    except ValueError:
        return False

    mover = chess.WHITE if move.color == "white" else chess.BLACK
    # A pawn moved if the pawn count on the mover's side is unchanged and the
    # piece counts of every other type are unchanged.
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        if len(before.pieces(piece_type, mover)) != len(after.pieces(piece_type, mover)):
            return False
    return len(before.pieces(chess.PAWN, mover)) == len(after.pieces(chess.PAWN, mover))
