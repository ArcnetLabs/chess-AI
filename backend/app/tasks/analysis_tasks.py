"""
Celery tasks for game analysis with retry logic.
"""
import asyncio
from datetime import datetime
from typing import List
from loguru import logger
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.analysis.unified_analyzer import UnifiedChessAnalyzer


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    name='app.tasks.analysis_tasks.analyze_game_task'
)
def analyze_game_task(self, game_id: int, user_id: int):
    """
    Celery task to analyze a single game with Stockfish.
    
    Args:
        game_id: ID of the game to analyze
        user_id: ID of the user who owns the game
        
    Returns:
        dict: Analysis result summary
        
    Retry Logic:
        - Max retries: 3
        - Initial delay: 60 seconds
        - Exponential backoff with jitter
        - Max delay: 600 seconds (10 minutes)
    """
    import time
    task_id = self.request.id
    db = SessionLocal()
    start_time = time.time()
    
    try:
        logger.info(f"🔍 [Task {task_id}] Starting Stockfish analysis for game {game_id}")
        
        # Get the game
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game or not game.pgn:
            logger.warning(f"❌ [Task {task_id}] Game {game_id} not found or has no PGN")
            return {"status": "failed", "reason": "Game not found or no PGN"}
        
        # Get user to determine color
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"❌ [Task {task_id}] User {user_id} not found")
            return {"status": "failed", "reason": "User not found"}
        
        # Determine user's color
        user_color = "white" if game.white_username and game.white_username.lower() == user.chesscom_username.lower() else "black"
        
        # Log game details
        opponent = game.black_username if user_color == "white" else game.white_username
        logger.info(f"🎮 [Task {task_id}] Game details - vs {opponent}, {game.time_class}, Result: {game.winner or 'draw'}")
        
        # Analyze game with UnifiedChessAnalyzer
        logger.info(f"🧠 [Task {task_id}] Analyzing game {game_id} with UnifiedChessAnalyzer (depth={settings.STOCKFISH_DEPTH})...")
        analysis_start = time.time()
        
        # Run async analysis in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def run_analysis():
                async with UnifiedChessAnalyzer() as analyzer:
                    return await analyzer.analyze_game(
                        pgn_string=game.pgn,
                        user_color=user_color,
                        game_id=str(game_id)
                    )
            
            result = loop.run_until_complete(run_analysis())
        finally:
            loop.close()
        
        analysis_time = time.time() - analysis_start
        logger.info(f"⏱️ [Task {task_id}] Analysis completed in {analysis_time:.2f} seconds")
        
        if not result:
            logger.warning(f"❌ [Task {task_id}] Analysis failed for game {game_id}")
            raise Exception(f"Analysis failed for game {game_id}")
        
        # Check if analysis already exists
        existing_analysis = db.query(GameAnalysis).filter(GameAnalysis.game_id == game_id).first()
        
        if existing_analysis:
            # Update existing analysis
            logger.info(f"📝 [Task {task_id}] Updating existing analysis for game {game_id}")
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
            # Create new analysis
            logger.info(f"✨ [Task {task_id}] Creating new analysis for game {game_id}")
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
        
        total_time = time.time() - start_time
        logger.info(
            f"✅ [Task {task_id}] Game {game_id} analyzed successfully in {total_time:.2f}s: "
            f"ACPL={result.user_acpl:.1f}, Accuracy={result.accuracy_percentage:.1f}%, "
            f"Blunders={result.blunders}, Mistakes={result.mistakes}, Inaccuracies={result.inaccuracies}"
        )
        
        return {
            "status": "success",
            "game_id": game_id,
            "user_acpl": result.user_acpl,
            "accuracy": result.accuracy_percentage,
            "blunders": result.blunders,
            "mistakes": result.mistakes,
            "analysis_time": total_time
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ [Task {task_id}] Error analyzing game {game_id}: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.warning(
                f"🔄 [Task {task_id}] Retrying game {game_id} analysis "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e)
        else:
            logger.error(f"💀 [Task {task_id}] Max retries reached for game {game_id}")
            return {
                "status": "failed",
                "game_id": game_id,
                "error": str(e),
                "retries": self.request.retries
            }
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='app.tasks.analysis_tasks.analyze_batch_games_task'
)
def analyze_batch_games_task(self, game_ids: List[int], user_id: int):
    """
    Celery task to queue multiple games for analysis.
    
    Args:
        game_ids: List of game IDs to analyze
        user_id: ID of the user who owns the games
        
    Returns:
        dict: Batch analysis summary
    """
    task_id = self.request.id
    
    try:
        logger.info(f"🔍 [Batch Task {task_id}] Queuing {len(game_ids)} games for analysis")
        
        # Queue individual analysis tasks
        task_results = []
        for game_id in game_ids:
            task = analyze_game_task.delay(game_id, user_id)
            task_results.append({
                "game_id": game_id,
                "task_id": task.id
            })
        
        logger.info(f"✅ [Batch Task {task_id}] Queued {len(task_results)} analysis tasks")
        
        return {
            "status": "success",
            "games_queued": len(task_results),
            "tasks": task_results
        }
        
    except Exception as e:
        logger.error(f"❌ [Batch Task {task_id}] Error queuing batch analysis: {str(e)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        else:
            return {
                "status": "failed",
                "error": str(e),
                "retries": self.request.retries
            }
