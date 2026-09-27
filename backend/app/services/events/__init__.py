"""Persistence for chess events (idempotent) and the events package entry point."""

from __future__ import annotations

from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.chess_event import ChessEvent
from app.models.game_move import GameMove

from .event_detector import detect_events_for_game


def persist_events(db: Session, events: List[Dict]) -> int:
    """Replace events for the games present in ``events``.

    Replace-not-merge keeps re-analysis honest: an event that a detector no
    longer produces disappears instead of lingering as stale coaching evidence.
    """
    if not events:
        return 0

    game_ids = {event["game_id"] for event in events}
    deleted = (
        db.query(ChessEvent)
        .filter(ChessEvent.game_id.in_(game_ids))
        .delete(synchronize_session=False)
    )
    db.add_all([ChessEvent(**event) for event in events])
    db.flush()
    logger.debug(
        f"chess_events: replaced {deleted} rows with {len(events)} for games {sorted(game_ids)}"
    )
    return len(events)


def detect_and_persist_events(
    db: Session,
    *,
    user_id: int,
    game_id: int,
    game_result: Optional[str],
    user_color: str,
) -> int:
    """Detect events for one game from its stored move facts and persist them.

    Returns the number of events written. Safe to call repeatedly.
    """
    moves = (
        db.query(GameMove)
        .filter(GameMove.user_id == user_id, GameMove.game_id == game_id)
        .order_by(GameMove.ply)
        .all()
    )
    if not moves:
        logger.debug(f"chess_events: no move facts for game={game_id}; nothing to detect")
        return 0

    events = detect_events_for_game(moves, game_result=game_result, user_color=user_color)
    return persist_events(db, events)


__all__ = ["detect_and_persist_events", "persist_events", "detect_events_for_game"]
