from typing import List, Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import User, Game, GameAnalysis
from ..services.tier_service import get_tier_service
from ..services.analysis.analysis_job_store import get_analysis_job_store
from ..services.analysis.analysis_status_stream import stream_job_status_events
from ..core.config import settings
from ..tasks.analysis_tasks import analyze_game_task, analyze_batch_games_task
from loguru import logger

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


class AnalysisJobStatusResponse(BaseModel):
    job_id: str
    user_id: int
    status: str
    source: str
    total_games: int
    completed_games: int
    failed_games: int
    pending_game_ids: List[int]
    current_game_id: Optional[int] = None
    created_at: str
    updated_at: str
    progress_percent: float


# Background analysis functions removed - now using Celery tasks
# See app/tasks/analysis_tasks.py for task implementations


def _job_status_response(job: dict) -> AnalysisJobStatusResponse:
    total = max(int(job.get("total_games", 0)), 1)
    completed = int(job.get("completed_games", 0))
    failed = int(job.get("failed_games", 0))
    progress = round(((completed + failed) / total) * 100, 1)
    return AnalysisJobStatusResponse(
        job_id=job["job_id"],
        user_id=job["user_id"],
        status=job["status"],
        source=job["source"],
        total_games=int(job.get("total_games", 0)),
        completed_games=completed,
        failed_games=failed,
        pending_game_ids=list(job.get("pending_game_ids", [])),
        current_game_id=job.get("current_game_id"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        progress_percent=progress,
    )


@router.post("/{user_id}/analyze/{game_id}")
async def analyze_single_game(
    user_id: int,
    game_id: int,
    force_reanalysis: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze a single game. Ownership-checked."""
    require_ownership(current_user, user_id)
    
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
        job_store = get_analysis_job_store()
        job_id = str(uuid4())
        job_store.create_job(
            job_id=job_id,
            user_id=user_id,
            game_ids=[game_id],
            source="single",
        )
        # Queue the analysis with Celery
        task = analyze_game_task.delay(game_id, user_id, job_id=job_id)
        logger.info(f"Queued Celery task {task.id} for game {game_id} (user {user_id})")
        
        return {
            "status": "queued",
            "message": "Analysis started (background)",
            "game_id": game_id,
            "task_id": task.id,
            "job_id": job_id,
        }
    except Exception as celery_error:
        logger.error(f"Celery queue failed for game {game_id}: {celery_error}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Analysis queue unavailable",
                "message": "Please try again in a few moments",
                "retry_after": 30,
            },
            headers={"Retry-After": "30"},
        )


@router.post("/{user_id}/analyze")
async def analyze_user_games(
    user_id: int,
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze games for a user with tier-aware logic. Ownership-checked."""
    require_ownership(current_user, user_id)
    
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
        task = analyze_batch_games_task.delay(
            game_ids_to_analyze,
            user_id,
            source="manual",
        )
        task_id = task.id
        job_id = task.id
    else:
        task_id = None
        job_id = None
    
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
        "job_id": job_id,
        "analysis_mode": analysis_mode,
        "uses_ai": uses_ai
    }


@router.get("/{user_id}/status", response_model=AnalysisJobStatusResponse)
async def get_active_analysis_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's active analysis job, if any."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    job = get_analysis_job_store().get_active_job(user_id)
    if not job:
        raise HTTPException(status_code=404, detail="No active analysis job")

    return _job_status_response(job)


@router.get("/{user_id}/status/stream")
async def stream_analysis_status(
    user_id: int,
    job_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream analysis job progress via Server-Sent Events.

    Pass ``job_id`` to follow a specific job; omit to follow the user's active job.
    Clients should use ``fetch`` with an ``Authorization`` header (EventSource cannot).
    """
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return StreamingResponse(
        stream_job_status_events(user_id, job_id=job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{user_id}/status/{job_id}", response_model=AnalysisJobStatusResponse)
async def get_analysis_job_status(
    user_id: int,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return status for a specific analysis job."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    job = get_analysis_job_store().get_job(job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    return _job_status_response(job)


@router.get("/{user_id}/analyses", response_model=List[AnalysisResponse])
async def get_user_analyses(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analysis results for a user's games. Ownership-checked."""
    require_ownership(current_user, user_id)
    
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
async def get_game_analysis(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analysis for a specific game. Game-ownership checked."""
    
    analysis = db.query(GameAnalysis).filter(GameAnalysis.game_id == game_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    # Enforce that the requester owns the underlying game.
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Analysis not found")
    require_ownership(current_user, game.user_id)
    
    return analysis


@router.get("/{user_id}/summary")
async def get_analysis_summary(
    user_id: int,
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analysis summary for a user. Ownership-checked."""
    require_ownership(current_user, user_id)
    
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
async def delete_game_analysis(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete analysis for a specific game. Game-ownership checked."""
    
    analysis = db.query(GameAnalysis).filter(GameAnalysis.game_id == game_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Analysis not found")
    require_ownership(current_user, game.user_id)
    game.is_analyzed = False
    
    db.delete(analysis)
    db.commit()
    
    return {"message": "Analysis deleted successfully"}
