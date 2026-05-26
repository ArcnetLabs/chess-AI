"""Canonical game analysis orchestration and persistence."""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.game import Game, GameAnalysis
from app.models.user import User

from .unified_analyzer import GameAnalysisResult, UnifiedChessAnalyzer


def resolve_user_color(game: Game, user: User) -> str:
    """Determine which side the linked Chess.com user played."""
    if (
        game.white_username
        and user.chesscom_username
        and game.white_username.lower() == user.chesscom_username.lower()
    ):
        return "white"
    return "black"


def persist_game_analysis(
    db: Session,
    game: Game,
    result: GameAnalysisResult,
    existing: Optional[GameAnalysis] = None,
) -> GameAnalysis:
    """Create or update ``GameAnalysis`` from a ``UnifiedChessAnalyzer`` result."""
    phase_fields = {
        "opening_acpl": result.opening_phase.average_acpl if result.opening_phase else None,
        "middlegame_acpl": result.middlegame_phase.average_acpl if result.middlegame_phase else None,
        "endgame_acpl": result.endgame_phase.average_acpl if result.endgame_phase else None,
    }

    if existing:
        existing.engine_version = result.engine_version
        existing.analysis_depth = result.analysis_depth
        existing.user_color = result.user_color
        existing.user_acpl = result.user_acpl
        existing.opponent_acpl = result.opponent_acpl
        existing.accuracy_percentage = result.accuracy_percentage
        existing.brilliant_moves = result.brilliant_moves
        existing.great_moves = result.great_moves
        existing.best_moves = result.best_moves
        existing.excellent_moves = result.excellent_moves
        existing.good_moves = result.good_moves
        existing.inaccuracies = result.inaccuracies
        existing.mistakes = result.mistakes
        existing.blunders = result.blunders
        existing.opening_name = result.opening_name
        existing.opening_eco = result.opening_eco
        for key, value in phase_fields.items():
            setattr(existing, key, value)
        analysis = existing
    else:
        analysis = GameAnalysis(
            game_id=game.id,
            engine_version=result.engine_version,
            analysis_depth=result.analysis_depth,
            user_color=result.user_color,
            user_acpl=result.user_acpl,
            opponent_acpl=result.opponent_acpl,
            accuracy_percentage=result.accuracy_percentage,
            brilliant_moves=result.brilliant_moves,
            great_moves=result.great_moves,
            best_moves=result.best_moves,
            excellent_moves=result.excellent_moves,
            good_moves=result.good_moves,
            inaccuracies=result.inaccuracies,
            mistakes=result.mistakes,
            blunders=result.blunders,
            opening_name=result.opening_name,
            opening_eco=result.opening_eco,
            **phase_fields,
        )
        db.add(analysis)

    game.is_analyzed = True
    db.commit()
    return analysis


async def analyze_game_for_user(
    game: Game,
    user: User,
    *,
    log_prefix: str = "",
) -> Optional[GameAnalysisResult]:
    """
    Run ``UnifiedChessAnalyzer`` for a stored game.

    Does not persist — callers use ``persist_game_analysis``.
    """
    if not game.pgn:
        logger.warning(f"{log_prefix}Game {game.id} has no PGN")
        return None

    user_color = resolve_user_color(game, user)
    opponent = game.black_username if user_color == "white" else game.white_username
    logger.info(
        f"{log_prefix}Analyzing game {game.id} vs {opponent}, "
        f"{game.time_class}, result={game.winner or 'draw'}"
    )

    async with UnifiedChessAnalyzer() as analyzer:
        return await analyzer.analyze_game(
            pgn_string=game.pgn,
            user_color=user_color,
            game_id=str(game.id),
        )
