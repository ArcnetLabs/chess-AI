"""
Celery tasks for game analysis with retry logic.
"""
import asyncio
from typing import List
from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.analysis.analysis_service import (
    analyze_game_for_user,
    persist_game_analysis,
)


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
    log_prefix = f"[Task {task_id}] "
    
    try:
        logger.info(f"🔍 {log_prefix}Starting Stockfish analysis for game {game_id}")
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game or not game.pgn:
            logger.warning(f"❌ {log_prefix}Game {game_id} not found or has no PGN")
            return {"status": "failed", "reason": "Game not found or no PGN"}
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"❌ {log_prefix}User {user_id} not found")
            return {"status": "failed", "reason": "User not found"}
        
        logger.info(
            f"🧠 {log_prefix}Analyzing game {game_id} with UnifiedChessAnalyzer "
            f"(depth={settings.STOCKFISH_DEPTH})..."
        )
        analysis_start = time.time()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                analyze_game_for_user(game, user, log_prefix=log_prefix)
            )
        finally:
            loop.close()
        
        analysis_time = time.time() - analysis_start
        logger.info(f"⏱️ {log_prefix}Analysis completed in {analysis_time:.2f} seconds")
        
        if not result:
            logger.warning(f"❌ {log_prefix}Analysis failed for game {game_id}")
            raise Exception(f"Analysis failed for game {game_id}")
        
        existing_analysis = db.query(GameAnalysis).filter(
            GameAnalysis.game_id == game_id
        ).first()
        
        if existing_analysis:
            logger.info(f"📝 {log_prefix}Updating existing analysis for game {game_id}")
        else:
            logger.info(f"✨ {log_prefix}Creating new analysis for game {game_id}")
        
        persist_game_analysis(db, game, result, existing=existing_analysis)
        
        total_time = time.time() - start_time
        logger.info(
            f"✅ {log_prefix}Game {game_id} analyzed successfully in {total_time:.2f}s: "
            f"ACPL={result.user_acpl:.1f}, Accuracy={result.accuracy_percentage:.1f}%, "
            f"Blunders={result.blunders}, Mistakes={result.mistakes}, "
            f"Inaccuracies={result.inaccuracies}"
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
        logger.error(f"❌ {log_prefix}Error analyzing game {game_id}: {str(e)}")
        
        if self.request.retries < self.max_retries:
            logger.warning(
                f"🔄 {log_prefix}Retrying game {game_id} analysis "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e)
        else:
            logger.error(f"💀 {log_prefix}Max retries reached for game {game_id}")
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
