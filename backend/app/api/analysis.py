from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.database import get_db, SessionLocal
from ..models import User, Game, GameAnalysis
from ..services.analysis.unified_analyzer import UnifiedChessAnalyzer
from ..services.tier_service import get_tier_service
from ..core.config import settings
from ..tasks.analysis_tasks import analyze_game_task, analyze_batch_games_task
from loguru import logger
import asyncio
from datetime import datetime

router = APIRouter()


class AnalysisResponse(BaseModel):
    id: int
    game_id: int
    engine_version: Optional[str]
    analysis_depth: Optional[int]
    analysis_time: Optional[float]
    user_color: Optional[str]
    user_acpl: Optional[float]
    opponent_acpl: Optional[float]
    brilliant_moves: int = 0
    great_moves: int = 0
    best_moves: int = 0
    excellent_moves: int = 0
    good_moves: int = 0
    inaccuracies: int = 0
    mistakes: int = 0
    blunders: int = 0
    opening_acpl: Optional[float]
    middlegame_acpl: Optional[float]
    endgame_acpl: Optional[float]
    opening_name: Optional[str]
    opening_eco: Optional[str]
    opening_moves: Optional[int]
    
    class Config:
        from_attributes = True


class AnalysisRequest(BaseModel):
    game_ids: Optional[List[int]] = None  # Specific games to analyze
    days: int = 7  # Analyze games from last N days
    time_classes: Optional[List[str]] = None  # Filter by time classes
    force_reanalysis: bool = False  # Re-analyze already analyzed games
    mode: str = "auto"  # "auto", "stockfish-only", or "ai-enhanced"


# Background analysis functions removed - now using Celery tasks
# See app/tasks/analysis_tasks.py for task implementations

async def analyze_game_background_DEPRECATED(game_id: int, user_id: int):
    """Background task to analyze a single game with Stockfish using UnifiedChessAnalyzer."""
    
    # Create new database session for background task
    db = SessionLocal()
    
    # Track analysis time
    from datetime import datetime
    start_time = datetime.now()
    
    try:
        logger.info(f"🔍 Starting Stockfish analysis for game {game_id}")
        
        # Get the game
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game or not game.pgn:
            logger.warning(f"Game {game_id} not found or has no PGN")
            return
        
        # Get user to determine color
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User {user_id} not found")
            return
        
        # Determine user's color
        user_color = "white" if game.white_username and game.white_username.lower() == user.chesscom_username.lower() else "black"
        
        # Analyze game with UnifiedChessAnalyzer
        logger.info(f"🧠 Analyzing game {game_id} with UnifiedChessAnalyzer (depth={settings.STOCKFISH_DEPTH})...")
        async with UnifiedChessAnalyzer() as analyzer:
            result = await analyzer.analyze_game(
                pgn_string=game.pgn,
                user_color=user_color,
                game_id=str(game_id)
            )
        
        if not result:
            logger.warning(f"❌ Analysis failed for game {game_id}")
            return
        
        # Check if analysis already exists
        existing_analysis = db.query(GameAnalysis).filter(GameAnalysis.game_id == game_id).first()
        
        if existing_analysis:
            # Update existing analysis with new UnifiedChessAnalyzer results
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
        else:
            # Create new analysis with UnifiedChessAnalyzer results
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
                endgame_acpl=result.endgame_phase.average_acpl if result.endgame_phase else None
            )
            
            db.add(analysis)
        
        # Mark game as analyzed
        game.is_analyzed = True
        
        db.commit()
        
        # Calculate analysis duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(
            f"✅ Game {game_id} analyzed successfully: "
            f"ACPL={result.user_acpl:.1f}, Accuracy={result.accuracy_percentage:.1f}%, "
            f"Blunders={result.blunders}, Mistakes={result.mistakes} | "
            f"⏱️ Time: {duration:.1f}s"
        )
        
    except Exception as e:
        logger.error(f"❌ Error analyzing game {game_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


@router.post("/{user_id}/analyze/{game_id}")
async def analyze_single_game(
    user_id: int,
    game_id: int,
    force_reanalysis: bool = False,
    db: Session = Depends(get_db)
):
    """Analyze a single game."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify game exists and belongs to user
    game = db.query(Game).filter(
        Game.id == game_id,
        Game.user_id == user_id
    ).first()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check if already analyzed
    existing_analysis = db.query(GameAnalysis).filter(
        GameAnalysis.game_id == game_id
    ).first()
    
    if existing_analysis and not force_reanalysis:
        return {
            "status": "already_analyzed",
            "message": "Game already analyzed",
            "game_id": game_id,
            "analysis_id": existing_analysis.id
        }
    
    # Try Celery first, fallback to synchronous analysis
    try:
        # Queue the analysis with Celery
        task = analyze_game_task.delay(game_id, user_id)
        logger.info(f"Queued Celery task {task.id} for game {game_id} (user {user_id})")
        
        return {
            "status": "queued",
            "message": "Analysis started (background)",
            "game_id": game_id,
            "task_id": task.id
        }
    except Exception as celery_error:
        # Celery not available, run synchronously
        logger.warning(f"Celery not available, running synchronous analysis: {celery_error}")
        
        try:
            # Run analysis synchronously
            from ..services.engine.stockfish_engine import StockfishEngine
            
            # Create and initialize Stockfish engine
            engine = StockfishEngine(depth=18, threads=2)
            await engine.initialize()
            
            # Create analyzer with engine
            analyzer = UnifiedChessAnalyzer(engine=engine)
            
            # Determine user color
            user_color = 'white' if game.white_player.lower() == user.chesscom_username.lower() else 'black'
            
            # Analyze the game
            analysis_result = await analyzer.analyze_game(
                pgn_string=game.pgn,
                user_color=user_color,
                game_id=str(game_id)
            )
            
            # Save analysis to database
            game_analysis = GameAnalysis(
                game_id=game_id,
                analyzed_at=datetime.utcnow(),
                accuracy_white=analysis_result.get('accuracy_white', 0),
                accuracy_black=analysis_result.get('accuracy_black', 0),
                mistakes_white=analysis_result.get('mistakes_white', 0),
                mistakes_black=analysis_result.get('mistakes_black', 0),
                blunders_white=analysis_result.get('blunders_white', 0),
                blunders_black=analysis_result.get('blunders_black', 0),
                analysis_data=analysis_result.get('moves', [])
            )
            
            if existing_analysis:
                # Update existing
                existing_analysis.analyzed_at = datetime.utcnow()
                existing_analysis.accuracy_white = game_analysis.accuracy_white
                existing_analysis.accuracy_black = game_analysis.accuracy_black
                existing_analysis.mistakes_white = game_analysis.mistakes_white
                existing_analysis.mistakes_black = game_analysis.mistakes_black
                existing_analysis.blunders_white = game_analysis.blunders_white
                existing_analysis.blunders_black = game_analysis.blunders_black
                existing_analysis.analysis_data = game_analysis.analysis_data
            else:
                db.add(game_analysis)
            
            # Mark game as analyzed
            game.analyzed = True
            db.commit()
            
            # Close engine
            await engine.close()
            
            logger.info(f"Synchronous analysis completed for game {game_id}")
            
            return {
                "status": "completed",
                "message": "Analysis completed successfully",
                "game_id": game_id,
                "analysis_id": existing_analysis.id if existing_analysis else game_analysis.id,
                "accuracy_white": game_analysis.accuracy_white,
                "accuracy_black": game_analysis.accuracy_black
            }
            
        except Exception as analysis_error:
            logger.error(f"Synchronous analysis failed for game {game_id}: {analysis_error}")
            # Try to close engine if it was created
            try:
                if 'engine' in locals():
                    await engine.close()
            except:
                pass
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {str(analysis_error)}"
            )


@router.post("/{user_id}/analyze")
async def analyze_user_games(
    user_id: int,
    request: AnalysisRequest,
    db: Session = Depends(get_db)
):
    """Analyze games for a user with tier-aware logic."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check tier status
    tier_service = get_tier_service(db)
    
    # Determine analysis mode based on tier and request
    analysis_mode = request.mode
    uses_ai = False
    
    if analysis_mode == "auto":
        # Auto mode: use AI if user can, otherwise Stockfish-only
        if tier_service.can_use_ai_analysis(user):
            analysis_mode = "ai-enhanced"
            uses_ai = True
        else:
            analysis_mode = "stockfish-only"
    elif analysis_mode == "ai-enhanced":
        # Explicit AI request: check if user has access
        if not tier_service.can_use_ai_analysis(user):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "AI analysis limit reached",
                    "message": tier_service.get_upgrade_message(user),
                    "tier": user.tier,
                    "remaining_analyses": user.remaining_ai_analyses,
                    "upgrade_required": True
                }
            )
        uses_ai = True
    
    # Build query for games to analyze
    if request.game_ids:
        # Analyze specific games
        games_query = db.query(Game).filter(
            Game.user_id == user_id,
            Game.id.in_(request.game_ids)
        )
    else:
        # Analyze ALL games for the user (not just recent ones)
        logger.info(f"Analyzing all games for user {user_id}")
        games_query = db.query(Game).filter(
            Game.user_id == user_id
        )
        
        if request.time_classes:
            games_query = games_query.filter(Game.time_class.in_(request.time_classes))
    
    # Filter out already analyzed games if not forcing re-analysis
    if not request.force_reanalysis:
        games_query = games_query.filter(Game.is_analyzed == False)
    
    games_to_analyze = games_query.all()
    
    if not games_to_analyze:
        return {
            "message": "No games to analyze",
            "games_queued": 0
        }
    
    # Increment AI usage if using AI-enhanced mode
    if uses_ai:
        if not tier_service.increment_ai_usage(user):
            raise HTTPException(
                status_code=403,
                detail="AI analysis limit reached"
            )
    
    # Queue analysis tasks with Celery
    game_ids_to_analyze = [game.id for game in games_to_analyze if game.pgn]
    
    if game_ids_to_analyze:
        task = analyze_batch_games_task.delay(game_ids_to_analyze, user_id)
        task_id = task.id
    else:
        task_id = None
    
    # Update user's analyzed_games count
    user.analyzed_games = db.query(Game).filter(
        Game.user_id == user_id,
        Game.is_analyzed == True
    ).count() + len(games_to_analyze)
    db.commit()
    
    return {
        "message": f"Queued {len(game_ids_to_analyze)} games for analysis",
        "games_queued": len(game_ids_to_analyze),
        "task_id": task_id,
        "analysis_mode": analysis_mode,
        "uses_ai": uses_ai
    }


@router.get("/{user_id}/analyses", response_model=List[AnalysisResponse])
async def get_user_analyses(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get analysis results for a user's games."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get analyses for user's games
    analyses = db.query(GameAnalysis).join(Game).filter(
        Game.user_id == user_id
    ).order_by(GameAnalysis.created_at.desc()).offset(skip).limit(limit).all()
    
    return analyses


@router.get("/game/{game_id}", response_model=AnalysisResponse)
async def get_game_analysis(game_id: int, db: Session = Depends(get_db)):
    """Get analysis for a specific game."""
    
    analysis = db.query(GameAnalysis).filter(GameAnalysis.game_id == game_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis


@router.get("/{user_id}/summary")
async def get_analysis_summary(user_id: int, days: int = 7, db: Session = Depends(get_db)):
    """Get analysis summary for a user."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get recent analyses
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get all analyzed games (don't filter by date if no games found in period)
    analyses = db.query(GameAnalysis).join(Game).filter(
        Game.user_id == user_id,
        Game.is_analyzed == True
    ).all()
    
    # If we have analyses, filter by date for the summary
    if analyses:
        recent_analyses = [a for a in analyses if a.game.end_time and a.game.end_time >= cutoff_date]
        # If no recent analyses, use all analyses
        if not recent_analyses:
            recent_analyses = analyses
            logger.info(f"No analyses in last {days} days, using all {len(analyses)} analyzed games")
        analyses = recent_analyses
    
    if not analyses:
        return {
            "period_days": days,
            "total_games_analyzed": 0,
            "message": "No analyzed games found for this period"
        }
    
    # Calculate summary statistics
    total_games = len(analyses)
    total_acpl = sum(a.user_acpl for a in analyses if a.user_acpl) / total_games if total_games > 0 else 0
    
    # Aggregate move counts
    move_totals = {
        'brilliant_moves': sum(a.brilliant_moves for a in analyses),
        'great_moves': sum(a.great_moves for a in analyses),
        'best_moves': sum(a.best_moves for a in analyses),
        'excellent_moves': sum(a.excellent_moves for a in analyses),
        'good_moves': sum(a.good_moves for a in analyses),
        'inaccuracies': sum(a.inaccuracies for a in analyses),
        'mistakes': sum(a.mistakes for a in analyses),
        'blunders': sum(a.blunders for a in analyses),
    }
    
    # Phase performance
    opening_acpl = sum(a.opening_acpl for a in analyses if a.opening_acpl) / len([a for a in analyses if a.opening_acpl]) if any(a.opening_acpl for a in analyses) else 0
    middlegame_acpl = sum(a.middlegame_acpl for a in analyses if a.middlegame_acpl) / len([a for a in analyses if a.middlegame_acpl]) if any(a.middlegame_acpl for a in analyses) else 0
    endgame_acpl = sum(a.endgame_acpl for a in analyses if a.endgame_acpl) / len([a for a in analyses if a.endgame_acpl]) if any(a.endgame_acpl for a in analyses) else 0
    
    # Common openings
    opening_counts = {}
    for analysis in analyses:
        if analysis.opening_name:
            opening_counts[analysis.opening_name] = opening_counts.get(analysis.opening_name, 0) + 1
    
    most_played_openings = sorted(opening_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Get tier info
    tier_service = get_tier_service(db)
    tier_status = tier_service.get_tier_status(user)
    
    return {
        "period_days": days,
        "total_games_analyzed": total_games,
        "average_acpl": round(total_acpl, 1),
        "move_quality_breakdown": move_totals,
        "phase_performance": {
            "opening_acpl": round(opening_acpl, 1),
            "middlegame_acpl": round(middlegame_acpl, 1),
            "endgame_acpl": round(endgame_acpl, 1)
        },
        "most_played_openings": most_played_openings,
        "accuracy_percentage": round(max(0, min(100, 100 - (total_acpl / 10))), 1),
        "tier_status": tier_status,
        "analysis_note": "Stockfish metrics only" if not tier_status["can_use_ai"] and user.tier == "free" else "Full AI insights"
    }


@router.delete("/game/{game_id}")
async def delete_game_analysis(game_id: int, db: Session = Depends(get_db)):
    """Delete analysis for a specific game."""
    
    analysis = db.query(GameAnalysis).filter(GameAnalysis.game_id == game_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Also mark the game as not analyzed
    game = db.query(Game).filter(Game.id == game_id).first()
    if game:
        game.is_analyzed = False
    
    db.delete(analysis)
    db.commit()
    
    return {"message": "Analysis deleted successfully"}
    return {"message": "Analysis deleted successfully"}
