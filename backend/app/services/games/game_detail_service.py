"""Game detail assembly for move exploration (P2-GV-01)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess
from sqlalchemy.orm import Session

from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.analysis.analysis_service import resolve_user_color
from app.services.analysis.pgn_parser import PGNParser

OPENING_END_DIVISOR = 3
OPENING_MAX_MOVES = 20
ENDGAME_MIN_GAP = 10


def _phase_boundaries(total_moves: int) -> Dict[str, tuple[int, int]]:
    raw_opening = total_moves // OPENING_END_DIVISOR if total_moves else 0
    opening_end = min(OPENING_MAX_MOVES, max(2, raw_opening or 2))
    endgame_start = max(opening_end + ENDGAME_MIN_GAP, (total_moves * 2) // 3)
    if endgame_start <= opening_end:
        endgame_start = opening_end + 1

    return {
        "opening": (1, opening_end),
        "middlegame": (opening_end, endgame_start),
        "endgame": (endgame_start, total_moves + 1),
    }


def _phase_for_move(move_number: int, boundaries: Dict[str, tuple[int, int]]) -> str:
    for phase, (start, end) in boundaries.items():
        if start <= move_number < end:
            return phase
    return "endgame"


def _build_phase_markers(
    analysis: Optional[GameAnalysis],
    total_moves: int,
) -> List[Dict[str, Any]]:
    boundaries = _phase_boundaries(total_moves)
    acpl_by_phase = {
        "opening": getattr(analysis, "opening_acpl", None) if analysis else None,
        "middlegame": getattr(analysis, "middlegame_acpl", None) if analysis else None,
        "endgame": getattr(analysis, "endgame_acpl", None) if analysis else None,
    }

    markers: List[Dict[str, Any]] = []
    for phase, (start, end) in boundaries.items():
        markers.append(
            {
                "phase": phase,
                "start_move": start,
                "end_move": min(end - 1, total_moves) if total_moves else end - 1,
                "average_acpl": acpl_by_phase.get(phase),
            }
        )
    return markers


def _annotate_moves_with_phase(
    moves: List[Dict[str, Any]],
    boundaries: Dict[str, tuple[int, int]],
) -> List[Dict[str, Any]]:
    annotated: List[Dict[str, Any]] = []
    for move in moves:
        payload = dict(move)
        move_number = int(payload.get("move_number") or 0)
        payload["phase"] = _phase_for_move(move_number, boundaries)
        annotated.append(payload)
    return annotated


def _pgn_moves_fallback(game: Game, user: User) -> List[Dict[str, Any]]:
    if not game.pgn:
        return []

    parsed = PGNParser.parse_pgn(game.pgn)
    if parsed is None:
        return []

    user_color = resolve_user_color(game, user)
    rows: List[Dict[str, Any]] = []
    board = parsed.board()
    move_number = 1

    for move in parsed.mainline_moves():
        is_white = board.turn == chess.WHITE
        is_user_move = (user_color == "white" and is_white) or (
            user_color == "black" and not is_white
        )
        fen_before = board.fen()
        san = board.san(move)
        board.push(move)
        rows.append(
            {
                "move_number": move_number,
                "move_san": san,
                "move_uci": move.uci(),
                "fen_before": fen_before,
                "fen_after": board.fen(),
                "evaluation_cp": None,
                "evaluation_change": None,
                "classification": None,
                "best_move_uci": None,
                "is_user_move": is_user_move,
            }
        )
        if board.turn == chess.WHITE:
            move_number += 1

    return rows


def _analysis_summary(analysis: GameAnalysis) -> Dict[str, Any]:
    return {
        "id": analysis.id,
        "user_color": analysis.user_color,
        "user_acpl": analysis.user_acpl,
        "opponent_acpl": analysis.opponent_acpl,
        "accuracy_percentage": analysis.accuracy_percentage,
        "opening_name": analysis.opening_name,
        "opening_eco": analysis.opening_eco,
        "opening_moves": analysis.opening_moves,
        "phase_acpl": {
            "opening": analysis.opening_acpl,
            "middlegame": analysis.middlegame_acpl,
            "endgame": analysis.endgame_acpl,
        },
        "move_quality": {
            "brilliant_moves": analysis.brilliant_moves,
            "great_moves": analysis.great_moves,
            "best_moves": analysis.best_moves,
            "excellent_moves": analysis.excellent_moves,
            "good_moves": analysis.good_moves,
            "inaccuracies": analysis.inaccuracies,
            "mistakes": analysis.mistakes,
            "blunders": analysis.blunders,
        },
        "critical_positions": analysis.critical_positions or [],
        "blunder_moves": analysis.blunder_moves or [],
    }


def _game_payload(game: Game) -> Dict[str, Any]:
    return {
        "id": game.id,
        "chesscom_game_id": game.chesscom_game_id,
        "chesscom_url": game.chesscom_url,
        "time_class": game.time_class,
        "time_control": game.time_control,
        "white_username": game.white_username,
        "black_username": game.black_username,
        "white_rating": game.white_rating,
        "black_rating": game.black_rating,
        "white_result": game.white_result,
        "black_result": game.black_result,
        "winner": game.winner,
        "start_time": game.start_time.isoformat() if game.start_time else None,
        "end_time": game.end_time.isoformat() if game.end_time else None,
        "is_analyzed": game.is_analyzed,
        "pgn": game.pgn,
        "fen": game.fen,
    }


def get_game_detail(db: Session, game: Game, user: User) -> Dict[str, Any]:
    """Build enriched game detail with moves, evals, and phase markers."""
    analysis = (
        db.query(GameAnalysis).filter(GameAnalysis.game_id == game.id).first()
        if game.is_analyzed
        else None
    )

    if analysis and analysis.evaluations:
        moves = list(analysis.evaluations)
    else:
        moves = _pgn_moves_fallback(game, user)

    total_moves = max((int(m.get("move_number") or 0) for m in moves), default=0)
    boundaries = _phase_boundaries(total_moves or 1)
    moves = _annotate_moves_with_phase(moves, boundaries)

    return {
        "game": _game_payload(game),
        "analysis": _analysis_summary(analysis) if analysis else None,
        "moves": moves,
        "phase_markers": _build_phase_markers(analysis, total_moves),
    }
