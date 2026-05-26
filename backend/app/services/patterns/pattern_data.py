"""Load Stockfish-grounded analysis aggregates for pattern detection."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.game import Game, GameAnalysis

from .types import PatternAggregationInput


def load_pattern_aggregation_input(
    db: Session,
    user_id: int,
    *,
    limit: Optional[int] = None,
) -> Optional[PatternAggregationInput]:
    """
    Build aggregation input from persisted game analyses.

    Does not invoke Stockfish — reads only ``GameAnalysis`` fields produced by
    ``UnifiedChessAnalyzer`` via ``analysis_service.persist_game_analysis``.
    """
    query = (
        db.query(GameAnalysis, Game)
        .join(Game, GameAnalysis.game_id == Game.id)
        .filter(
            Game.user_id == user_id,
            Game.is_analyzed.is_(True),
        )
        .order_by(Game.end_time.desc().nullslast(), GameAnalysis.created_at.desc())
    )
    if limit is not None:
        query = query.limit(limit)

    rows = query.all()
    if not rows:
        return None

    opening_acpls: list[float] = []
    middlegame_acpls: list[float] = []
    endgame_acpls: list[float] = []
    opening_by_game: list[dict] = []

    for analysis, game in rows:
        if analysis.opening_acpl is not None:
            opening_acpls.append(analysis.opening_acpl)
        if analysis.middlegame_acpl is not None:
            middlegame_acpls.append(analysis.middlegame_acpl)
        if analysis.endgame_acpl is not None:
            endgame_acpls.append(analysis.endgame_acpl)

        opening_by_game.append(
            {
                "game_id": game.id,
                "opening_name": analysis.opening_name,
                "opening_eco": analysis.opening_eco,
                "opening_acpl": analysis.opening_acpl,
                "middlegame_acpl": analysis.middlegame_acpl,
                "endgame_acpl": analysis.endgame_acpl,
                "user_acpl": analysis.user_acpl,
                "played_at": game.end_time.isoformat() if game.end_time else None,
            }
        )

    return PatternAggregationInput(
        user_id=user_id,
        total_analyzed_games=len(rows),
        opening_acpls=opening_acpls,
        middlegame_acpls=middlegame_acpls,
        endgame_acpls=endgame_acpls,
        opening_by_game=opening_by_game,
    )
