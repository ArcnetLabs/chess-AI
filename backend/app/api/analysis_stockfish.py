"""
Updated Analysis API using UnifiedChessAnalyzer with Stockfish.

This is a new implementation that uses the unified Stockfish integration.
You can replace the old analysis.py with this once tested.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio

from ..core.database import get_db, SessionLocal
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import User, Game, GameAnalysis
from ..services.analysis.unified_analyzer import UnifiedChessAnalyzer
from ..core.config import settings
from loguru import logger

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalysisRequest(BaseModel):
    """Request to analyze games."""
    game_ids: Optional[List[int]] = None  # Specific games to analyze
    max_games: int = 10  # Maximum number of games to analyze
    force_reanalysis: bool = False  # Re-analyze already analyzed games


class AnalysisResponse(BaseModel):
    """Analysis result for a single game."""
    id: int
    game_id: int
    user_color: str
    
    # Overall metrics
    user_acpl: float
    opponent_acpl: Optional[float]
    accuracy_percentage: float
    
    # Move quality
    brilliant_moves: int = 0
    best_moves: int = 0
    good_moves: int = 0
    inaccuracies: int = 0
    mistakes: int = 0
    blunders: int = 0
    
    # Phase analysis
    opening_acpl: Optional[float]
    middlegame_acpl: Optional[float]
    endgame_acpl: Optional[float]
    
    # Opening info
    opening_name: Optional[str]
    opening_eco: Optional[str]
    
    # Metadata
    engine_version: str
    analysis_depth: int
    analyzed_at: datetime
    
    class Config:
        from_attributes = True


class AnalysisQueueResponse(BaseModel):
    """Response when games are queued for analysis."""
    status: str
    games_queued: int
    message: str


# ============================================================================
# Background Analysis Task
# ============================================================================

def analyze_game_background_wrapper(game_id: int, user_id: int):
    """Wrapper to run async analysis in background task."""
    asyncio.run(analyze_game_background(game_id, user_id))


async def analyze_game_background(game_id: int, user_id: int):
    """
    Background task to analyze a single game with Stockfish.
    
    This function:
    1. Fetches the game from database
    2. Determines user's color
    3. Analyzes with UnifiedChessAnalyzer
    4. Saves results to database
    """
    
    # Create new database session for background task
    db = SessionLocal()
    
    try:
        logger.info(f"Starting Stockfish analysis for game {game_id}")
        
        # Fetch game
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game or not game.pgn:
            logger.warning(f"Game {game_id} not found or has no PGN")
            return
        
        # Fetch user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User {user_id} not found")
            return
        
        # Determine user's color
        user_color = "white" if game.white_username and game.white_username.lower() == user.chesscom_username.lower() else "black"
        
        # Analyze game with UnifiedChessAnalyzer
        async with UnifiedChessAnalyzer() as analyzer:
            result = await analyzer.analyze_game(
                pgn_string=game.pgn,
                user_color=user_color,
                game_id=str(game_id)
            )
        
        if not result:
            logger.warning(f"Analysis failed for game {game_id}")
            return
        
        # Check if analysis already exists
        existing_analysis = db.query(GameAnalysis).filter(
            GameAnalysis.game_id == game_id
        ).first()
        
        if existing_analysis:
            # Update existing analysis
            logger.info(f"Updating existing analysis for game {game_id}")
            existing_analysis.engine_version = result.engine_version
            existing_analysis.analysis_depth = result.analysis_depth
            existing_analysis.user_color = result.user_color
            existing_analysis.user_acpl = result.user_acpl
            existing_analysis.opponent_acpl = result.opponent_acpl
            existing_analysis.accuracy_percentage = result.accuracy_percentage
            existing_analysis.brilliant_moves = result.brilliant_moves
            existing_analysis.great_moves = result.great_moves
            existing_analysis.best_moves = result.best_moves
            existing_analysis.excellent_moves = result.excellent_moves
            existing_analysis.good_moves = result.good_moves
            existing_analysis.inaccuracies = result.inaccuracies
            existing_analysis.mistakes = result.mistakes
            existing_analysis.blunders = result.blunders
            existing_analysis.opening_name = result.opening_name
            existing_analysis.opening_eco = result.opening_eco
            existing_analysis.opening_acpl = result.opening_phase.average_acpl if result.opening_phase else None
            existing_analysis.middlegame_acpl = result.middlegame_phase.average_acpl if result.middlegame_phase else None
            existing_analysis.endgame_acpl = result.endgame_phase.average_acpl if result.endgame_phase else None
            existing_analysis.analysis_data = result.to_dict()
            existing_analysis.analyzed_at = datetime.utcnow()
        else:
            # Create new analysis
            logger.info(f"Creating new analysis for game {game_id}")
            analysis = GameAnalysis(
                game_id=game_id,
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
                opening_acpl=result.opening_phase.average_acpl if result.opening_phase else None,
                middlegame_acpl=result.middlegame_phase.average_acpl if result.middlegame_phase else None,
                endgame_acpl=result.endgame_phase.average_acpl if result.endgame_phase else None,
                analysis_data=result.to_dict(),
                analyzed_at=datetime.utcnow()
            )
            db.add(analysis)
        
        # Mark game as analyzed
        game.is_analyzed = True
        
        db.commit()
        logger.info(
            f"✅ Game {game_id} analyzed: ACPL={result.user_acpl:.1f}, "
            f"Accuracy={result.accuracy_percentage:.1f}%, Blunders={result.blunders}"
        )
        
    except Exception as e:
        logger.error(f"❌ Error analyzing game {game_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/{user_id}/analyze", response_model=AnalysisQueueResponse)
async def analyze_user_games(
    user_id: int,
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue games for Stockfish analysis.
    
    This endpoint:
    1. Finds games to analyze (either specific games or recent unanalyzed games)
    2. Queues them for background analysis
    3. Returns immediately with queue status
    
    The actual analysis happens in the background.
    """
    require_ownership(current_user, user_id)
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build query for games to analyze
    query = db.query(Game).filter(Game.user_id == user_id)
    
    # Filter by specific game IDs if provided
    if request.game_ids:
        query = query.filter(Game.id.in_(request.game_ids))
    else:
        # Only analyze games that haven't been analyzed yet
        if not request.force_reanalysis:
            query = query.filter(Game.is_analyzed == False)
    
    # Limit number of games
    games_to_analyze = query.limit(request.max_games).all()
    
    if not games_to_analyze:
        return AnalysisQueueResponse(
            status="no_games",
            games_queued=0,
            message="No games found to analyze"
        )
    
    # Queue each game for background analysis
    for game in games_to_analyze:
        background_tasks.add_task(
            analyze_game_background_wrapper,
            game.id,
            user_id
        )
    
    logger.info(f"Queued {len(games_to_analyze)} games for analysis (user {user_id})")
    
    return AnalysisQueueResponse(
        status="queued",
        games_queued=len(games_to_analyze),
        message=f"Analyzing {len(games_to_analyze)} games in background. Check back in a few minutes."
    )


@router.get("/{user_id}/games/{game_id}/analysis", response_model=AnalysisResponse)
async def get_game_analysis(
    user_id: int,
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get analysis results for a specific game.
    
    Returns detailed analysis including:
    - Overall metrics (ACPL, accuracy)
    - Move quality breakdown
    - Phase analysis (opening/middlegame/endgame)
    - Opening information
    """
    require_ownership(current_user, user_id)
    
    # Fetch analysis
    analysis = db.query(GameAnalysis).filter(
        GameAnalysis.game_id == game_id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found. Game may not be analyzed yet."
        )
    
    # Verify game belongs to user
    game = db.query(Game).filter(Game.id == game_id, Game.user_id == user_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return analysis


@router.get("/{user_id}/analysis/summary")
async def get_analysis_summary(
    user_id: int,
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get summary statistics across all analyzed games.
    
    Returns:
    - Average ACPL
    - Average accuracy
    - Total blunders/mistakes/inaccuracies
    - Phase-specific statistics
    - Trends over time
    """
    require_ownership(current_user, user_id)
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all analyzed games for user
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    analyses = db.query(GameAnalysis).join(Game).filter(
        Game.user_id == user_id,
        GameAnalysis.analyzed_at >= cutoff_date
    ).all()
    
    if not analyses:
        return {
            "status": "no_data",
            "message": "No analyzed games found",
            "total_games": 0
        }
    
    # Calculate summary statistics
    total_games = len(analyses)
    avg_acpl = sum(a.user_acpl for a in analyses if a.user_acpl) / total_games
    avg_accuracy = sum(a.accuracy_percentage for a in analyses if a.accuracy_percentage) / total_games
    
    total_blunders = sum(a.blunders for a in analyses)
    total_mistakes = sum(a.mistakes for a in analyses)
    total_inaccuracies = sum(a.inaccuracies for a in analyses)
    total_best_moves = sum(a.best_moves for a in analyses)
    
    # Phase statistics
    opening_acpls = [a.opening_acpl for a in analyses if a.opening_acpl]
    middlegame_acpls = [a.middlegame_acpl for a in analyses if a.middlegame_acpl]
    endgame_acpls = [a.endgame_acpl for a in analyses if a.endgame_acpl]
    
    return {
        "status": "success",
        "period_days": days,
        "total_games": total_games,
        "overall": {
            "average_acpl": round(avg_acpl, 1),
            "average_accuracy": round(avg_accuracy, 1),
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_inaccuracies": total_inaccuracies,
            "total_best_moves": total_best_moves,
            "blunders_per_game": round(total_blunders / total_games, 1),
            "mistakes_per_game": round(total_mistakes / total_games, 1)
        },
        "phase_analysis": {
            "opening": {
                "average_acpl": round(sum(opening_acpls) / len(opening_acpls), 1) if opening_acpls else None,
                "games_analyzed": len(opening_acpls)
            },
            "middlegame": {
                "average_acpl": round(sum(middlegame_acpls) / len(middlegame_acpls), 1) if middlegame_acpls else None,
                "games_analyzed": len(middlegame_acpls)
            },
            "endgame": {
                "average_acpl": round(sum(endgame_acpls) / len(endgame_acpls), 1) if endgame_acpls else None,
                "games_analyzed": len(endgame_acpls)
            }
        }
    }


@router.delete("/{user_id}/games/{game_id}/analysis")
async def delete_game_analysis(
    user_id: int,
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete analysis for a specific game. Ownership-checked."""
    require_ownership(current_user, user_id)
    
    # Verify game belongs to user
    game = db.query(Game).filter(Game.id == game_id, Game.user_id == user_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Delete analysis
    analysis = db.query(GameAnalysis).filter(GameAnalysis.game_id == game_id).first()
    if analysis:
        db.delete(analysis)
        game.is_analyzed = False
        db.commit()
        return {"status": "deleted", "game_id": game_id}
    
    raise HTTPException(status_code=404, detail="Analysis not found")
