"""Invariant audit of stored move facts.

    python scripts/audit_move_facts.py --user-id 1
    python scripts/audit_move_facts.py --user-id 1 --limit 20000 --json audit.json

Why this exists: a wrong sentence in a coach context ("you played f2f4, better was
b8c6" — a Black move, offered to White) turned out to be a stored field holding the
opponent's reply for **every** ply. One bad sentence, a library-wide defect. This
script checks the substrate the same way, so the next one is found by running a
command rather than by reading a reply closely.

It compares stored rows against each other and against the positions they claim to
describe, with no engine call, so it runs anywhere against any environment.

**Conventions it encodes** (getting these wrong produces thousands of phantom
violations — the first version of this script reported 5,830 of them):

* ``eval_before_cp``/``eval_after_cp`` are in the **mover's own** perspective, so a
  ply's ``eval_before`` is the *negation* of the previous ply's ``eval_after``.
* ``cp_loss`` is ``max(0, eval_before - eval_after)``: a gaining move records zero.

**Known legacy state:** rows written before the best-move fix store the *opponent's*
best reply. They are reported as ``best_move_is_opponents_reply`` and are expected
until those games are re-analysed; presentation suppresses them, so no player sees
them. Any *other* violation in the summary is a real finding.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.game_move import GameMove  # noqa: E402
from app.services.analysis.position_features import (  # noqa: E402
    position_key as position_key_of,
)
from app.services.analysis.position_features import (  # noqa: E402
    structure_key as structure_key_of,
)

# Expected on rows written before the best-move fix; everything else is a finding.
KNOWN_LEGACY = {"best_move_is_opponents_reply"}
EXIT_OK = 0
EXIT_VIOLATIONS = 1


# A principal variation may be stored as a space-separated string, a JSON list, or a
# Python-repr list (``"['c7c5', 'g8f6']"``) — all three occur. Splitting on whitespace
# "found" 269 violations that were entirely an artefact of the checker reading
# ``"['c7c5',"`` as a move, so the first UCI token is extracted instead.
_UCI = re.compile(r"[a-h][1-8][a-h][1-8][qrbn]?")


def _first_pv_move(pv) -> str:
    text = pv if isinstance(pv, str) else str(pv)
    match = _UCI.search(text)
    return match.group(0) if match else ""


def audit(db, user_id: int, limit: int) -> Dict:
    moves: List[GameMove] = (
        db.query(GameMove)
        .filter(GameMove.user_id == user_id)
        .order_by(GameMove.game_id, GameMove.ply)
        .limit(limit)
        .all()
    )

    counts: Counter = Counter()
    examples: Dict[str, List] = defaultdict(list)

    def note(kind: str, detail) -> None:
        counts[kind] += 1
        if len(examples[kind]) < 3:
            examples[kind].append(detail)

    by_game: Dict[int, List[GameMove]] = defaultdict(list)
    for move in moves:
        by_game[move.game_id].append(move)

        try:
            board = chess.Board(move.fen_before)
        except Exception:
            note("fen_unparseable", move.id)
            continue

        if move.position_key and move.position_key != position_key_of(board):
            note("position_key_mismatch", (move.id, move.ply))
        if move.structure_key and move.structure_key != structure_key_of(board):
            note("structure_key_mismatch", (move.id, move.ply))

        turn = "white" if board.turn == chess.WHITE else "black"
        if move.color and move.color != turn:
            note("colour_vs_fen_mismatch", (move.id, move.ply, move.color, turn))

        if move.move_uci:
            try:
                if chess.Move.from_uci(move.move_uci) not in board.legal_moves:
                    note("played_move_illegal", (move.id, move.ply, move.move_uci))
            except Exception:
                note("move_uci_unparseable", (move.id, move.move_uci))

        if (
            move.cp_loss is not None
            and move.eval_before_cp is not None
            and move.eval_after_cp is not None
        ):
            expected = max(0.0, float(move.eval_before_cp) - float(move.eval_after_cp))
            if abs(expected - float(move.cp_loss)) > 1.0:
                note("cp_loss_disagrees_with_evals", (move.id, move.cp_loss, round(expected, 1)))

        if bool(move.is_mate_score) != (move.mate_in is not None):
            note("mate_flag_vs_mate_in", (move.id, move.is_mate_score, move.mate_in))

        if move.best_pv and move.best_move_uci:
            first = _first_pv_move(move.best_pv)
            if first and first != move.best_move_uci:
                note("pv_first_vs_best_move", (move.id, first, move.best_move_uci))

        if move.best_move_uci:
            try:
                best = chess.Move.from_uci(move.best_move_uci)
                if best not in board.legal_moves:
                    after = chess.Board(move.fen_after)
                    if best in after.legal_moves:
                        note("best_move_is_opponents_reply", (move.id, move.ply))
                    else:
                        note("best_move_illegal_anywhere", (move.id, move.ply, move.best_move_uci))
            except Exception:
                note("best_move_unparseable", (move.id, move.best_move_uci))

    for game_id, game_moves in by_game.items():
        ordered = sorted(game_moves, key=lambda m: m.ply)
        for previous, current in zip(ordered, ordered[1:]):
            if current.ply != previous.ply + 1:
                note("ply_gap", (game_id, previous.ply, current.ply))
            if (
                previous.eval_after_cp is not None
                and current.eval_before_cp is not None
                # Negated: same position, opposite mover (see the module docstring).
                and abs(float(previous.eval_after_cp) + float(current.eval_before_cp)) > 1.0
            ):
                note(
                    "eval_discontinuity",
                    (game_id, previous.ply, previous.eval_after_cp, current.eval_before_cp),
                )
            if current.prev_ply is not None and current.prev_ply != previous.ply:
                note("prev_ply_mismatch", (game_id, current.ply, current.prev_ply, previous.ply))

    unexpected = {kind: value for kind, value in counts.items() if kind not in KNOWN_LEGACY}
    return {
        "user_id": user_id,
        "rows": len(moves),
        "counts": dict(counts.most_common()),
        "known_legacy": {k: v for k, v in counts.items() if k in KNOWN_LEGACY},
        "unexpected": unexpected,
        "examples": {k: v for k, v in examples.items() if k in unexpected},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--json", help="write the full report to this path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = audit(db, args.user_id, args.limit)
    finally:
        db.close()

    print(f"rows audited: {report['rows']}")
    if not report["counts"]:
        print("no violations found")
    else:
        print("\nviolations (known legacy first):")
        for kind, value in report["counts"].items():
            tag = "expected" if kind in KNOWN_LEGACY else "FINDING"
            print(f"  [{tag:8}] {kind}: {value}")

    for kind, items in report["examples"].items():
        print(f"\nexamples of {kind}:")
        for item in items:
            print(f"  {item}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"\nwrote {args.json}")

    return EXIT_VIOLATIONS if report["unexpected"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
