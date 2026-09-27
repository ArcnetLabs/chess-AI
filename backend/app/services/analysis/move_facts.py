"""Build and persist per-move facts from an analysis result.

Why this module exists
----------------------
Per-move facts used to live only in JSON on ``game_analyses``. Detectors had to
re-flatten those blobs on every run, and none of the position context pattern
recognition needs (position identity, structure, material, threats) existed
anywhere. This module turns one analysis result into ``game_moves`` rows.

Evaluation conventions (important, and verified against the analyzer)
---------------------------------------------------------------------
``MoveAnalysis.evaluation_cp`` is **black-centric**, not raw engine output: the
analyzer flips the sign for Black's moves (``unified_analyzer.py:294-296``), so
the stored value is the engine eval after the move *from Black's point of view*
either way. Mate positions were flattened to ``0`` by ``or 0``
(``unified_analyzer.py:283``), but ``mate_in`` keeps the truth, so mates are
reconstructed here instead of counting as a quiet position.

Derived, per move, in the moving side's own perspective:

* ``eval_before_cp`` — the engine eval of the position the mover was facing,
  taken from the previous ply's post-move evaluation (the same position, so no
  extra engine call is needed).
* ``eval_after_cp``  — the engine eval after the move.
* ``cp_loss``        — ``eval_before - eval_after``, clamped at zero. This is
  the eval drop attributable to the move itself, which is what
  ``evaluation_change`` failed to express because it mixed perspectives.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import chess
from loguru import logger
from sqlalchemy.orm import Session

from app.models.game_move import GameMove

from .phase_boundaries import phase_for_move
from .position_features import (
    extract_features,
    material_balance,
    position_key,
    structure_key,
)

# Mate is scored as decisive but *bounded*. A raw +/-10000 makes centipawn
# statistics meaningless — one mate flip swamps every average and saturates every
# severity band — so mate is mapped to a value clearly above any real material
# swing while staying in a sane range.
#
# IMPORTANT: mate rows are reconstructed from ``mate_in`` (the analyzer flattened
# ``evaluation_cp`` to 0 for mates), and that reconstruction has not been
# independently verified against the engine wrapper's sign convention. Live data
# showed mate-derived cp_loss disagreeing with the analyzer's own move
# classification in 607 of 711 mate rows, so the event detector refuses to build
# coaching claims on a mate row unless the analyzer independently agrees the move
# was a serious error. See ``is_mate_score``.
MATE_SCORE = 1200.0


def _eval_after_black_centric(move, mover: str) -> float:
    """Post-move evaluation in Black-centric centipawns, mate-aware.

    ``mate_in`` is reported from the side to move *after* the move, i.e. the
    mover's opponent, which is what fixes the sign here.
    """
    if move.mate_in is not None:
        # Opponent mates when mate_in > 0; otherwise the mover is mating.
        opponent_mates = move.mate_in > 0
        if mover == "white":
            return MATE_SCORE if opponent_mates else -MATE_SCORE
        return -MATE_SCORE if opponent_mates else MATE_SCORE

    return float(move.evaluation_cp or 0)


def _mover_perspective(black_centric: float, mover: str) -> float:
    """Convert Black-centric centipawns into the mover's own perspective."""
    return black_centric if mover == "black" else -black_centric


def build_move_facts(
    *,
    user_id: int,
    game_id: int,
    user_color: str,
    moves: Iterable,
    engine_depth: Optional[int] = None,
) -> List[Dict]:
    """Turn analyzer ``MoveAnalysis`` entries into ``game_moves`` row dicts."""
    plies = list(moves)
    total_plies = len(plies)
    rows: List[Dict] = []

    # Eval of the position before ply 1 (the initial position, level by definition).
    previous_mover_eval = 0.0

    for ply, move in enumerate(plies, start=1):
        mover = "white" if ply % 2 == 1 else "black"
        black_centric_after = _eval_after_black_centric(move, mover)
        mover_eval_after = _mover_perspective(black_centric_after, mover)

        # The position the mover faced is the position after the previous ply,
        # evaluated from the opponent's perspective there.
        mover_eval_before = -previous_mover_eval
        cp_loss = max(0.0, mover_eval_before - mover_eval_after)

        try:
            board_before = chess.Board(move.fen_before)
            features = extract_features(board_before, mover=(mover == "white"))
            key = position_key(board_before)
            structure = structure_key(board_before)
            balance = material_balance(board_before)
        except ValueError:
            # A malformed FEN should not lose the move row; the engine evidence
            # is still useful, and the feature columns are nullable by design.
            logger.warning(
                f"game_moves: could not derive position features for game={game_id} ply={ply}"
            )
            features, key, structure, balance = {}, None, None, None

        rows.append(
            {
                "user_id": user_id,
                "game_id": game_id,
                "ply": ply,
                "move_number": (ply + 1) // 2,
                "color": mover,
                "is_user_move": mover == user_color,
                "fen_before": move.fen_before,
                "fen_after": move.fen_after,
                "position_key": key,
                "structure_key": structure,
                "material_balance": balance,
                "move_uci": move.move_uci,
                "move_san": move.move_san,
                "best_move_uci": move.best_move_uci,
                "best_pv": getattr(move, "pv", None),
                "eval_before_cp": round(mover_eval_before, 1),
                "eval_after_cp": round(mover_eval_after, 1),
                "cp_loss": round(cp_loss, 1),
                "mate_in": move.mate_in,
                "is_mate_score": move.mate_in is not None,
                "engine_depth": engine_depth,
                "classification": move.classification,
                "phase": phase_for_move(ply, total_plies),
                "features": features,
                "prev_ply": ply - 1 if ply > 1 else None,
            }
        )

        previous_mover_eval = mover_eval_after

    return rows


def persist_move_facts(db: Session, rows: List[Dict]) -> int:
    """Replace the stored move facts for the games present in ``rows``.

    Replacing rather than merging keeps re-analysis and backfill honest: a move
    that no longer exists (or whose evidence changed) cannot linger. Events hang
    off ``game_moves`` with ``ON DELETE CASCADE``, so they are rebuilt too.
    """
    if not rows:
        return 0

    game_ids = {row["game_id"] for row in rows}
    deleted = (
        db.query(GameMove)
        .filter(GameMove.game_id.in_(game_ids))
        .delete(synchronize_session=False)
    )
    db.add_all([GameMove(**row) for row in rows])
    db.flush()
    logger.debug(
        f"game_moves: replaced {deleted} rows with {len(rows)} for games {sorted(game_ids)}"
    )
    return len(rows)


def load_move_facts(db: Session, user_id: int, game_id: int) -> List[GameMove]:
    """Move facts for one game, in ply order."""
    return (
        db.query(GameMove)
        .filter(GameMove.user_id == user_id, GameMove.game_id == game_id)
        .order_by(GameMove.ply)
        .all()
    )


class _PayloadMove:
    """Adapter exposing the fields ``build_move_facts`` reads.

    The stored ``evaluations`` payload keeps the analyzer's field names, so the
    same builder can consume both live results and backfilled JSON.
    """

    __slots__ = (
        "move_number",
        "move_san",
        "move_uci",
        "fen_before",
        "fen_after",
        "evaluation_cp",
        "mate_in",
        "best_move_uci",
        "evaluation_change",
        "classification",
        "is_user_move",
        "pv",
    )

    def __init__(self, payload: Dict):
        self.move_number = payload.get("move_number")
        self.move_san = payload.get("move_san") or ""
        self.move_uci = payload.get("move_uci") or ""
        self.fen_before = payload.get("fen_before")
        self.fen_after = payload.get("fen_after")
        self.evaluation_cp = payload.get("evaluation_cp")
        self.mate_in = payload.get("mate_in")
        self.best_move_uci = payload.get("best_move_uci")
        self.evaluation_change = payload.get("evaluation_change")
        self.classification = payload.get("classification") or "good"
        self.is_user_move = bool(payload.get("is_user_move"))
        self.pv = payload.get("pv")


def moves_from_payload(payload: Optional[Iterable[Dict]]) -> List[_PayloadMove]:
    """Convert a stored ``evaluations`` payload into move objects.

    Rows without FENs are skipped: without them there is no position to key or
    describe, and inventing one would put fabricated evidence into the layer
    that pattern detection treats as ground truth.
    """
    moves: List[_PayloadMove] = []
    for entry in payload or []:
        if not isinstance(entry, dict):
            continue
        if not entry.get("fen_before") or not entry.get("fen_after"):
            continue
        moves.append(_PayloadMove(entry))
    return moves
