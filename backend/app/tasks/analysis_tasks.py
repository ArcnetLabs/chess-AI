"""
Celery tasks for game analysis with retry logic.
"""
import asyncio
from typing import List, Optional
from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.analysis.analysis_service import (
    analyze_game_for_user,
    persist_game_analysis,
    persist_move_layer,
    resolve_user_color,
)
from app.services.analysis.analysis_job_store import get_analysis_job_store
from app.services.analysis.pgn_preflight import preflight_error
from app.services.analysis.unified_analyzer import AnalysisCancelledError
from app.services.engine.engine_pool import StockfishEnginePool
from app.tasks.pattern_tasks import schedule_pattern_detection_for_user
from app.tasks.profile_tasks import (
    PROFILE_BUILD_DEBOUNCE_COUNTDOWN_SECONDS,
    schedule_profile_build_for_user,
)


async def _analyze_with_engine_cleanup(
    game: Game,
    user: User,
    log_prefix: str,
    should_cancel,
):
    """Analyze one game and release its Stockfish process before closing the loop."""
    try:
        return await analyze_game_for_user(
            game,
            user,
            log_prefix=log_prefix,
            should_cancel=should_cancel,
        )
    finally:
        await StockfishEnginePool.shutdown()


def _force_final_passes(user_id: int, log_prefix: str) -> None:
    """End-of-batch trigger for the pattern and profile snapshots.

    Per-game triggers are debounced, so without an explicit end-of-batch signal
    the snapshots the reveal headlines can lag the finished run by the whole
    debounce window. A batch whose last game *failed* or was skipped ends just
    as surely as one whose last game succeeded, so it needs the same trigger.
    """
    logger.info(
        f"{log_prefix}Job finished — forcing final pattern detection "
        f"and profile build for user {user_id}"
    )
    schedule_pattern_detection_for_user(user_id, countdown=5, force=True)
    # The profile build is debounced separately, so the build the last
    # detection scheduled mid-run suppresses the final one. Queue it behind the
    # detection (solo worker, ETA order) so the snapshot the reveal headlines
    # reflects the completed run.
    schedule_profile_build_for_user(
        user_id,
        countdown=PROFILE_BUILD_DEBOUNCE_COUNTDOWN_SECONDS,
        force=True,
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
def analyze_game_task(self, game_id: int, user_id: int, job_id: Optional[str] = None):
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
    job_store = get_analysis_job_store()
    
    try:
        logger.info(f"🔍 {log_prefix}Starting Stockfish analysis for game {game_id}")
        if job_store.is_cancelled(job_id):
            return {"status": "cancelled", "game_id": game_id}
        job_store.mark_game_running(job_id, game_id)
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game or not game.pgn:
            logger.warning(f"❌ {log_prefix}Game {game_id} not found or has no PGN")
            if job_store.mark_game_failed(
                job_id, game_id, error="Game not found or has no PGN"
            ):
                _force_final_passes(user_id, log_prefix)
            return {"status": "failed", "reason": "Game not found or no PGN"}

        if game.is_analyzed:
            logger.info(f"{log_prefix}Game {game_id} is already analyzed; marking complete")
            job_store.mark_game_completed(job_id, game_id)
            return {"status": "already_analyzed", "game_id": game_id}

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"❌ {log_prefix}User {user_id} not found")
            job_store.mark_game_failed(job_id, game_id, error="User not found")
            return {"status": "failed", "reason": "User not found"}

        # Chess.com stores a row for games that never produced a move (aborted
        # tournament pairings). Nothing to analyze — and that is deterministic,
        # so it must not enter the 3-attempt / 60s retry ladder: the retries
        # cost ~2 minutes of worker time and fail identically each time.
        #
        # The same applies to a game with movetext but none of it the player's:
        # a one-ply aborted game the player had Black in has nothing of theirs
        # to score, and analysing it anyway stored 0.0 ACPL / 99.0% accuracy for
        # a game they never moved in (game 2750). Which colour the player had is
        # needed to tell that from a normal short game, hence the user lookup
        # above this check.
        user_color = resolve_user_color(game, user)
        refusal = preflight_error(game.pgn, user_color)
        if refusal:
            logger.warning(f"⏭️ {log_prefix}Game {game_id}: {refusal}; skipping")
            if job_store.mark_game_failed(job_id, game_id, error=refusal):
                _force_final_passes(user_id, log_prefix)
            return {"status": "skipped", "game_id": game_id, "reason": "no_moves"}

        logger.info(
            f"🧠 {log_prefix}Analyzing game {game_id} with UnifiedChessAnalyzer "
            f"(depth={settings.STOCKFISH_DEPTH})..."
        )
        analysis_start = time.time()
        
        result = asyncio.run(
            _analyze_with_engine_cleanup(
                game,
                user,
                log_prefix,
                should_cancel=lambda: job_store.is_cancelled(job_id),
            )
        )

        if job_store.is_cancelled(job_id):
            return {"status": "cancelled", "game_id": game_id}
        
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

        # Per-move facts and chess events — the substrate pattern detection
        # reads. Failure here must not lose the analysis that was just saved:
        # the backfill script can rebuild this layer from the stored JSON.
        try:
            persist_move_layer(db, game, user, result)
        except Exception as move_exc:  # noqa: BLE001
            db.rollback()
            logger.error(
                f"⚠️ {log_prefix}Move/event layer failed for game {game_id}: {move_exc}"
            )
        
        total_time = time.time() - start_time
        logger.info(
            f"✅ {log_prefix}Game {game_id} analyzed successfully in {total_time:.2f}s: "
            f"ACPL={result.user_acpl:.1f}, Accuracy={result.accuracy_percentage:.1f}%, "
            f"Blunders={result.blunders}, Mistakes={result.mistakes}, "
            f"Inaccuracies={result.inaccuracies}"
        )

        # Per-game triggers are debounced, so the last game of a batch also
        # forces the final detection pass: otherwise the pattern/profile
        # snapshots can lag the finished analysis by the whole debounce window
        # while the UI already reports the full game count.
        job_finished = job_store.mark_game_completed(job_id, game_id)
        if job_finished:
            _force_final_passes(user_id, log_prefix)
        else:
            schedule_pattern_detection_for_user(user_id)

        return {
            "status": "success",
            "game_id": game_id,
            "user_acpl": result.user_acpl,
            "accuracy": result.accuracy_percentage,
            "blunders": result.blunders,
            "mistakes": result.mistakes,
            "analysis_time": total_time
        }
        
    except AnalysisCancelledError:
        db.rollback()
        logger.info(f"{log_prefix}Analysis cancelled for game {game_id}")
        return {"status": "cancelled", "game_id": game_id}
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
            if job_store.mark_game_failed(job_id, game_id, error=str(e)):
                _force_final_passes(user_id, log_prefix)
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
def analyze_batch_games_task(
    self,
    game_ids: List[int],
    user_id: int,
    source: str = "batch",
    job_id: Optional[str] = None,
):
    """
    Celery task to queue multiple games for analysis.
    
    Args:
        game_ids: List of game IDs to analyze
        user_id: ID of the user who owns the games
        
    Returns:
        dict: Batch analysis summary
    """
    task_id = job_id or self.request.id

    try:
        logger.info(f"🔍 [Batch Task {task_id}] Queuing {len(game_ids)} games for analysis")

        job_store = get_analysis_job_store()
        if not job_store.get_job(task_id):
            job_store.create_job(
                job_id=task_id,
                user_id=user_id,
                game_ids=game_ids,
                source=source,
            )
        
        task_results = []
        for game_id in game_ids:
            task = analyze_game_task.delay(game_id, user_id, job_id=task_id)
            task_results.append({
                "game_id": game_id,
                "task_id": task.id
            })
        
        logger.info(f"✅ [Batch Task {task_id}] Queued {len(task_results)} analysis tasks")
        
        return {
            "status": "success",
            "job_id": task_id,
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
