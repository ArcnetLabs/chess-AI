"""Coach context handoff from game positions (P2-GV-04)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.user import User
from app.services.games.game_detail_service import get_game_detail

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _select_move_context(
    moves: list[Dict[str, Any]],
    move_number: Optional[int],
) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    if not moves:
        return None, move_number

    if move_number is not None:
        for move in moves:
            if int(move.get("move_number") or 0) == move_number:
                return move, move_number
        return None, move_number

    return moves[-1], int(moves[-1].get("move_number") or len(moves))


def resolve_handoff_fen(
    detail: Dict[str, Any],
    move_number: Optional[int] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Resolve the FEN and move metadata for a coach handoff."""
    game = detail.get("game") or {}
    moves = detail.get("moves") or []
    move_ctx, requested_move = _select_move_context(moves, move_number)

    if move_ctx:
        fen = move_ctx.get("fen_before") or move_ctx.get("fen_after")
        if fen:
            return fen, move_ctx

    if game.get("fen"):
        return game["fen"], move_ctx

    if moves:
        last = moves[-1]
        fen = last.get("fen_after") or last.get("fen_before")
        if fen:
            return fen, move_ctx

    return STARTING_FEN, move_ctx


def build_suggested_message(
    detail: Dict[str, Any],
    move_ctx: Optional[Dict[str, Any]],
) -> str:
    analysis = detail.get("analysis") or {}
    opening = analysis.get("opening_name")

    if move_ctx and move_ctx.get("move_san"):
        move_san = move_ctx["move_san"]
        classification = move_ctx.get("classification")
        if classification in {"mistake", "blunder"}:
            return (
                f"Can you explain why {move_san} was a {classification} in this game"
                f"{f' ({opening})' if opening else ''}?"
            )
        if classification:
            return (
                f"What should I have played instead of {move_san} "
                f"({classification}) in this position?"
            )
        return f"Analyze this position after {move_san} and suggest a plan."

    if opening:
        return f"Analyze this position from my {opening} game and suggest a plan."

    return "Analyze this position from my game and suggest a plan."


def build_coach_handoff(
    db: Session,
    game: Game,
    user: User,
    *,
    move_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Build coach handoff payload for a game position."""
    detail = get_game_detail(db, game, user)
    moves = detail.get("moves") or []

    if move_number is not None and moves:
        if not any(int(m.get("move_number") or 0) == move_number for m in moves):
            raise LookupError(f"Move {move_number} not found in game")

    fen, move_ctx = resolve_handoff_fen(detail, move_number)
    analysis = detail.get("analysis")

    return {
        "game_id": game.id,
        "move_number": (
            int(move_ctx.get("move_number"))
            if move_ctx and move_ctx.get("move_number") is not None
            else move_number
        ),
        "move_san": move_ctx.get("move_san") if move_ctx else None,
        "classification": move_ctx.get("classification") if move_ctx else None,
        "phase": move_ctx.get("phase") if move_ctx else None,
        "fen": fen,
        "suggested_message": build_suggested_message(detail, move_ctx),
        "opening_name": analysis.get("opening_name") if analysis else None,
        "user_color": analysis.get("user_color") if analysis else None,
    }
