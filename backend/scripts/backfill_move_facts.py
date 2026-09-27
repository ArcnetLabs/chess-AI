"""Backfill ``game_moves`` and ``chess_events`` from stored analysis JSON.

Existing analyses predate the move/event layer, so pattern detection has no
history to work with until this runs. It reads the ``evaluations`` payload that
``persist_game_analysis`` has always written, rebuilds per-move facts (including
position keys, structure keys, material and features) and re-derives events.

Idempotent: each game's rows are replaced, so it is safe to re-run after a
change to the feature set or the event vocabulary.

Usage (from ``backend/``)::

    python scripts/backfill_move_facts.py --user-id 1
    python scripts/backfill_move_facts.py --limit 25 --dry-run

Not part of the pytest suite (see ``AGENTS.md``): diagnostic/manual tooling.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.chess_event import ChessEvent  # noqa: E402
from app.models.game import Game, GameAnalysis  # noqa: E402
from app.models.game_move import GameMove  # noqa: E402
from app.services.analysis.move_facts import (  # noqa: E402
    build_move_facts,
    moves_from_payload,
    persist_move_facts,
)
from app.services.events import detect_and_persist_events  # noqa: E402


def backfill(*, user_id: int | None, limit: int | None, dry_run: bool) -> dict:
    db = SessionLocal()
    stats = {"games": 0, "moves": 0, "events": 0, "skipped": 0}
    try:
        query = (
            db.query(GameAnalysis, Game)
            .join(Game, Game.id == GameAnalysis.game_id)
            .order_by(GameAnalysis.id)
        )
        if user_id is not None:
            query = query.filter(Game.user_id == user_id)
        if limit is not None:
            query = query.limit(limit)

        for analysis, game in query.all():
            moves = moves_from_payload(analysis.evaluations or [])
            if not moves:
                stats["skipped"] += 1
                logger.warning(
                    f"backfill: game {game.id} has no usable move payload; skipped"
                )
                continue

            user_color = analysis.user_color or "white"
            rows = build_move_facts(
                user_id=game.user_id,
                game_id=game.id,
                user_color=user_color,
                moves=moves,
                engine_depth=analysis.analysis_depth,
            )

            if dry_run:
                stats["games"] += 1
                stats["moves"] += len(rows)
                continue

            persist_move_facts(db, rows)
            event_count = detect_and_persist_events(
                db,
                user_id=game.user_id,
                game_id=game.id,
                game_result=game.winner,
                user_color=user_color,
            )
            db.commit()

            stats["games"] += 1
            stats["moves"] += len(rows)
            stats["events"] += event_count
            logger.info(
                f"backfill: game {game.id} -> {len(rows)} moves, {event_count} events"
            )

        if dry_run:
            db.rollback()
    finally:
        db.close()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, default=None, help="only this user")
    parser.add_argument("--limit", type=int, default=None, help="max games to process")
    parser.add_argument(
        "--dry-run", action="store_true", help="report without writing anything"
    )
    args = parser.parse_args()

    stats = backfill(user_id=args.user_id, limit=args.limit, dry_run=args.dry_run)
    logger.info(
        f"backfill {'(dry run) ' if args.dry_run else ''}complete: "
        f"{stats['games']} games, {stats['moves']} moves, {stats['events']} events, "
        f"{stats['skipped']} skipped"
    )

    # Show what the layer looks like afterwards.
    if not args.dry_run:
        db = SessionLocal()
        try:
            total_moves = db.query(GameMove).count()
            total_events = db.query(ChessEvent).count()
            logger.info(f"totals: game_moves={total_moves}, chess_events={total_events}")
        finally:
            db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
