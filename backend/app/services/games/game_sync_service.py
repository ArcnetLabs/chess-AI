"""Chess.com game import — shared by API fetch and scheduled beat sync (P2-AA-05)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.user import User
from app.services.analysis.auto_analysis_service import queue_new_games_for_analysis
from app.services.filter_service import GameFilter, get_filter_service
from app.services.integration.chesscom_api import chesscom_api

SCHEDULED_SYNC_PREF_KEY = "scheduled_sync_enabled"
DEFAULT_SCHEDULED_SYNC = True
DRAW_RESULTS = frozenset({"agreed", "stalemate", "repetition", "insufficient"})


def is_scheduled_sync_enabled(user: User) -> bool:
    """Return whether this user should be included in beat-driven Chess.com pulls."""
    prefs = user.analysis_preferences or {}
    return bool(prefs.get(SCHEDULED_SYNC_PREF_KEY, DEFAULT_SCHEDULED_SYNC))


def determine_winner(
    white_result: Optional[str],
    black_result: Optional[str],
) -> Optional[str]:
    if white_result == "win":
        return "white"
    if black_result == "win":
        return "black"
    if white_result in DRAW_RESULTS:
        return "draw"
    return None


def persist_chesscom_games(
    db: Session,
    user: User,
    raw_games: Sequence[dict],
    *,
    time_classes: Optional[List[str]] = None,
    max_games: Optional[int] = None,
) -> Tuple[int, int, List[int]]:
    """Persist Chess.com payloads. Returns (added, updated, new_game_ids)."""
    games_added = 0
    games_updated = 0
    new_game_ids: List[int] = []

    for raw_game in raw_games:
        if max_games is not None and games_added >= max_games:
            break

        game_data = chesscom_api.parse_game_data(raw_game, user.chesscom_username)

        if time_classes and game_data["time_class"] not in time_classes:
            continue

        existing_game = (
            db.query(Game)
            .filter(Game.chesscom_game_id == game_data["chesscom_game_id"])
            .first()
        )
        if existing_game:
            games_updated += 1
            continue

        game = Game(
            user_id=user.id,
            chesscom_game_id=game_data["chesscom_game_id"],
            chesscom_url=game_data["chesscom_url"],
            time_class=game_data["time_class"],
            time_control=game_data["time_control"],
            rules=game_data["rules"],
            white_username=game_data["white_username"],
            black_username=game_data["black_username"],
            white_rating=game_data["white_rating"],
            black_rating=game_data["black_rating"],
            white_result=game_data["white_result"],
            black_result=game_data["black_result"],
            winner=determine_winner(
                game_data["white_result"],
                game_data["black_result"],
            ),
            pgn=game_data["pgn"],
            fen=game_data["fen"],
            start_time=game_data["start_time"],
            end_time=game_data["end_time"],
        )
        db.add(game)
        db.flush()
        new_game_ids.append(game.id)
        games_added += 1

    return games_added, games_updated, new_game_ids


async def import_chesscom_games(
    db: Session,
    user: User,
    *,
    days: Optional[int] = None,
    count: Optional[int] = None,
    source: str,
    time_classes: Optional[List[str]] = None,
    game_filter: Optional[GameFilter] = None,
    max_games: Optional[int] = None,
    auto_analyze_override: Optional[bool] = None,
) -> Dict[str, Any]:
    """Fetch from Chess.com, persist new games, and optionally queue analysis."""
    if not user.chesscom_username:
        return {
            "status": "skipped",
            "reason": "no_chesscom_username",
            "games_added": 0,
            "games_updated": 0,
            "analysis_queue": None,
        }

    raw_games = await chesscom_api.get_recent_games(
        user.chesscom_username,
        days=days,
        count=count,
        user_id=user.id,
    )

    if not raw_games:
        return {
            "status": "success",
            "games_added": 0,
            "games_updated": 0,
            "analysis_queue": None,
            "message": "No recent games found",
        }

    if game_filter is not None:
        filter_service = get_filter_service()
        raw_games = filter_service.apply_filters(raw_games, game_filter)

    games_added, games_updated, new_game_ids = persist_chesscom_games(
        db,
        user,
        raw_games,
        time_classes=time_classes,
        max_games=max_games,
    )

    db.commit()

    user.total_games = db.query(Game).filter(Game.user_id == user.id).count()
    db.commit()

    analysis_queue = queue_new_games_for_analysis(
        db,
        user,
        new_game_ids,
        source=source,
        request_override=auto_analyze_override,
    )

    logger.info(
        f"Chess.com import complete user={user.id} source={source} "
        f"added={games_added} updated={games_updated} queued={analysis_queue.get('games_queued', 0)}"
    )

    return {
        "status": "success",
        "games_added": games_added,
        "games_updated": games_updated,
        "new_game_ids": new_game_ids,
        "total_games": user.total_games,
        "analysis_queue": analysis_queue,
    }
