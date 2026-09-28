"""Recompute stored game phases under the material-aware rule.

    python scripts/recompute_phases.py --user-id 1 --dry-run
    python scripts/recompute_phases.py --user-id 1

`game_moves.phase` used to be decided by move number alone, so a position with queens on
and full material was called an endgame simply because enough moves had been played.
Phase is part of a pattern's identity (it is in the context signature and it gates
several event types), so the stored rows and everything derived from them have to agree.

This walks the three places a phase is stored — the move, its events, and its pattern
occurrences — from the position itself, and reports what changed. It calls no engine and
no model: the phase is a function of the position, which is already stored.

After running it, re-run pattern detection so pattern contexts are rebuilt from the new
phases:

    python -c "from app.core.database import SessionLocal; \
from app.services.patterns.pattern_engine import run_pattern_detection; \
db = SessionLocal(); run_pattern_detection(db, 1, persist=True)"

(``scripts/run_cli.py`` style helpers are deliberately avoided here: this is an
operational script, meant to be read before it is run.)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.chess_event import ChessEvent  # noqa: E402
from app.models.game_move import GameMove  # noqa: E402
from app.models.pattern import PatternOccurrence  # noqa: E402
from app.services.analysis.phase_boundaries import phase_for_position  # noqa: E402
from app.services.analysis.position_features import (  # noqa: E402
    extract_features,
    is_simplified,
)

EXIT_OK = 0
EXIT_DISAGREEMENT = 1


def _new_phase(row: GameMove, total_plies: int) -> str:
    """Phase of a stored move, computed from the position it was played from."""
    board = chess.Board(row.fen_before)
    simplified = is_simplified(board)
    features = {"simplified": simplified}
    return phase_for_position(row.ply, total_plies, features)


def recompute(db, user_id: int, *, dry_run: bool) -> Dict:
    moves: List[GameMove] = (
        db.query(GameMove).filter(GameMove.user_id == user_id).order_by(GameMove.game_id, GameMove.ply).all()
    )

    by_game: Dict[int, List[GameMove]] = defaultdict(list)
    for move in moves:
        by_game[move.game_id].append(move)

    transitions = Counter()
    stored_features_disagree = 0
    changed_moves: List[GameMove] = []

    for game_moves in by_game.values():
        total_plies = len(game_moves)
        for row in game_moves:
            try:
                new_phase = _new_phase(row, total_plies)
            except ValueError:
                continue
            stored = row.phase or "unknown"
            if (row.features or {}).get("simplified") not in (None, is_simplified(chess.Board(row.fen_before))):
                stored_features_disagree += 1
            if new_phase != stored:
                transitions[f"{stored} -> {new_phase}"] += 1
                changed_moves.append(row)
                if not dry_run:
                    row.phase = new_phase

    events_changed = occurrences_changed = 0
    if changed_moves and not dry_run:
        # Bulk updates, not row-by-row ORM writes. The first version assigned
        # `row.phase` per move and committed once, which meant one UPDATE per row —
        # thousands of round trips against a pooled remote database, and it did not
        # finish in ten minutes. `bulk_update_mappings` sends them as executemany.
        chunk_size = 500
        for start in range(0, len(changed_moves), chunk_size):
            chunk = changed_moves[start : start + chunk_size]
            db.bulk_update_mappings(
                GameMove,
                [{"id": row.id, "phase": row.phase} for row in chunk],
            )
            db.flush()
            print(f"  moves {start + len(chunk)}/{len(changed_moves)}", flush=True)

        changed_by_id = {row.id: row.phase for row in changed_moves}
        move_ids = list(changed_by_id)

        events = (
            db.query(ChessEvent.id, ChessEvent.move_id, ChessEvent.phase)
            .filter(ChessEvent.move_id.in_(move_ids))
            .all()
        )
        event_updates = [
            {"id": event.id, "phase": changed_by_id[event.move_id]}
            for event in events
            if event.move_id in changed_by_id and event.phase != changed_by_id[event.move_id]
        ]
        for start in range(0, len(event_updates), chunk_size):
            db.bulk_update_mappings(ChessEvent, event_updates[start : start + chunk_size])
            db.flush()
        events_changed = len(event_updates)

        occurrences = (
            db.query(PatternOccurrence.id, PatternOccurrence.move_id, PatternOccurrence.game_phase)
            .filter(PatternOccurrence.move_id.in_(move_ids))
            .all()
        )
        occurrence_updates = [
            {"id": occurrence.id, "game_phase": changed_by_id[occurrence.move_id]}
            for occurrence in occurrences
            if occurrence.move_id in changed_by_id
            and occurrence.game_phase != changed_by_id[occurrence.move_id]
        ]
        for start in range(0, len(occurrence_updates), chunk_size):
            db.bulk_update_mappings(
                PatternOccurrence, occurrence_updates[start : start + chunk_size]
            )
            db.flush()
        occurrences_changed = len(occurrence_updates)

        db.commit()

    return {
        "user_id": user_id,
        "moves": len(moves),
        "changed_moves": len(changed_moves),
        "transitions": dict(transitions),
        "events_changed": events_changed,
        "occurrences_changed": occurrences_changed,
        "stored_features_disagree": stored_features_disagree,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--json", help="write the report to this path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = recompute(db, args.user_id, dry_run=args.dry_run)
    finally:
        db.close()

    print(f"rows: {report['moves']}")
    print(f"moves relabelled: {report['changed_moves']}")
    for transition, value in sorted(report["transitions"].items(), key=lambda kv: -kv[1]):
        print(f"  {transition}: {value}")
    if not args.dry_run:
        print(f"events updated: {report['events_changed']}")
        print(f"pattern occurrences updated: {report['occurrences_changed']}")
    if report["stored_features_disagree"]:
        print(
            f"\nNOTE: stored `simplified` disagreed with the position in "
            f"{report['stored_features_disagree']} rows; the phase above was computed from "
            f"the position, not the stored feature."
        )
    if args.dry_run:
        print("\ndry run: nothing written")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"wrote {args.json}")

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
