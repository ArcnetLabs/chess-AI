from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.database import get_db
from ..models import User, Game, GameAnalysis, UserInsight

router = APIRouter()


class InsightResponse(BaseModel):
    id: int
    user_id: int
    period_start: datetime
    period_end: datetime
    analysis_type: str
    total_games: int
    games_analyzed: int
    average_acpl: Optional[float]
    performance_trend: Optional[str]
    rating_change: Optional[int]
    opening_performance: Optional[dict]
    middlegame_performance: Optional[dict]
    endgame_performance: Optional[dict]
    move_quality_stats: Optional[dict]
    frequent_mistakes: Optional[dict]
    recommendations: Optional[dict]
    
    class Config:
        from_attributes = True


class InsightRequest(BaseModel):
    period_days: int = 7
    analysis_type: str = "weekly"  # weekly, monthly, custom


async def generate_insights_background(user_id: int, period_start: datetime, period_end: datetime, analysis_type: str, db: Session):
    """Background task to generate insights for a user."""
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    
    # Get games and analyses for the period
    games = db.query(Game).filter(
        Game.user_id == user_id,
        Game.end_time >= period_start,
        Game.end_time <= period_end
    ).all()
    
    analyses = db.query(GameAnalysis).join(Game).filter(
        Game.user_id == user_id,
        Game.end_time >= period_start,
        Game.end_time <= period_end,
        Game.is_analyzed == True
    ).all()
    
    if not analyses:
        return
    
    # Calculate performance metrics
    total_games = len(games)
    games_analyzed = len(analyses)
    
    average_acpl = sum(a.user_acpl for a in analyses if a.user_acpl) / games_analyzed if games_analyzed > 0 else 0
    
    # Calculate rating change
    if games:
        first_game = min(games, key=lambda g: g.end_time or datetime.min)
        last_game = max(games, key=lambda g: g.end_time or datetime.min)
        
        # Get user's rating from first and last games
        first_rating = None
        last_rating = None
        
        if first_game.white_username.lower() == user.chesscom_username:
            first_rating = first_game.white_rating
        else:
            first_rating = first_game.black_rating
        
        if last_game.white_username.lower() == user.chesscom_username:
            last_rating = last_game.white_rating
        else:
            last_rating = last_game.black_rating
        
        rating_change = (last_rating - first_rating) if (first_rating and last_rating) else 0
    else:
        rating_change = 0
    
    # Determine performance trend
    if rating_change > 20:
        performance_trend = "improving"
    elif rating_change < -20:
        performance_trend = "declining"
    else:
        performance_trend = "stable"
    
    # Phase performance
    opening_acpls = [a.opening_acpl for a in analyses if a.opening_acpl]
    middlegame_acpls = [a.middlegame_acpl for a in analyses if a.middlegame_acpl]
    endgame_acpls = [a.endgame_acpl for a in analyses if a.endgame_acpl]
    
    opening_performance = {
        "acpl": sum(opening_acpls) / len(opening_acpls) if opening_acpls else 0,
        "games_count": len(opening_acpls)
    }
    
    middlegame_performance = {
        "acpl": sum(middlegame_acpls) / len(middlegame_acpls) if middlegame_acpls else 0,
        "games_count": len(middlegame_acpls)
    }
    
    endgame_performance = {
        "acpl": sum(endgame_acpls) / len(endgame_acpls) if endgame_acpls else 0,
        "games_count": len(endgame_acpls)
    }
    
    # Move quality statistics
    move_quality_stats = {
        'brilliant_moves': sum(a.brilliant_moves for a in analyses),
        'great_moves': sum(a.great_moves for a in analyses),
        'best_moves': sum(a.best_moves for a in analyses),
        'excellent_moves': sum(a.excellent_moves for a in analyses),
        'good_moves': sum(a.good_moves for a in analyses),
        'inaccuracies': sum(a.inaccuracies for a in analyses),
        'mistakes': sum(a.mistakes for a in analyses),
        'blunders': sum(a.blunders for a in analyses),
    }
    
    # Frequent mistakes analysis
    total_blunders = move_quality_stats['blunders']
    total_mistakes = move_quality_stats['mistakes']
    total_inaccuracies = move_quality_stats['inaccuracies']
    
    frequent_mistakes = [
        {"pattern": "Blunders", "count": total_blunders, "severity": "high"},
        {"pattern": "Mistakes", "count": total_mistakes, "severity": "medium"},
        {"pattern": "Inaccuracies", "count": total_inaccuracies, "severity": "low"},
    ]
    
    # Opening repertoire analysis
    opening_stats = {}
    for analysis in analyses:
        if analysis.opening_name:
            if analysis.opening_name not in opening_stats:
                opening_stats[analysis.opening_name] = {
                    "count": 0,
                    "total_acpl": 0,
                    "eco": analysis.opening_eco
                }
            opening_stats[analysis.opening_name]["count"] += 1
            opening_stats[analysis.opening_name]["total_acpl"] += analysis.user_acpl or 0
    
    # Calculate average ACPL for each opening
    for opening in opening_stats:
        if opening_stats[opening]["count"] > 0:
            opening_stats[opening]["average_acpl"] = opening_stats[opening]["total_acpl"] / opening_stats[opening]["count"]
    
    # Generate recommendations based on analysis
    recommendations = []
    recommendation_scores = []
    pattern_matches = []
    
    # Try to use enhanced recommendation engine
    try:
        from ..services.coaching.recommendation_engine import RecommendationEngine
        from loguru import logger
        
        engine = RecommendationEngine()
        enhanced_recommendations = engine.generate_recommendations(
            user_data={
                "user_id": user_id,
                "rating_change": rating_change,
                "performance_trend": performance_trend
            },
            analysis_data={
                "average_acpl": average_acpl,
                "opening_performance": opening_performance,
                "middlegame_performance": middlegame_performance,
                "endgame_performance": endgame_performance,
                "move_quality_stats": move_quality_stats,
                "frequent_mistakes": frequent_mistakes,
                "opening_stats": opening_stats,
                "total_games": games_analyzed
            },
            max_recommendations=5
        )
        
        # Use enhanced recommendations if available
        if enhanced_recommendations:
            recommendations = [rec.to_dict() for rec in enhanced_recommendations]
            recommendation_scores = [rec.priority_score for rec in enhanced_recommendations]
            pattern_matches = [
                rec.pattern_match.to_dict() 
                for rec in enhanced_recommendations 
                if rec.pattern_match
            ]
            logger.info(f"Generated {len(recommendations)} enhanced recommendations for user {user_id}")
        else:
            # Fallback to basic recommendations if no enhanced ones generated
            logger.info(f"No enhanced recommendations generated, using basic fallback for user {user_id}")
            raise Exception("No enhanced recommendations")
            
    except Exception as e:
        # Fallback to basic recommendations if enhanced engine fails
        from loguru import logger
        logger.warning(f"Enhanced recommendation engine failed, using basic recommendations: {e}")
        
        # ACPL-based recommendations (original logic)
        if average_acpl > 100:
            recommendations.append({
                "category": "tactics",
                "priority": "high",
                "description": f"Your average accuracy is {100 - (average_acpl/10):.1f}%. Focus on tactical training to reduce blunders."
            })
        
        if total_blunders > games_analyzed * 0.3:  # More than 30% of games have blunders
            recommendations.append({
                "category": "time_management",
                "priority": "high",
                "description": "You're making frequent blunders. Consider taking more time for critical moves."
            })
        
        # Phase-specific recommendations
        phase_acpls = [
            ("opening", opening_performance["acpl"]),
            ("middlegame", middlegame_performance["acpl"]),
            ("endgame", endgame_performance["acpl"])
        ]
        
        worst_phase = max(phase_acpls, key=lambda x: x[1])
        if worst_phase[1] > 80:
            recommendations.append({
                "category": f"{worst_phase[0]}_study",
                "priority": "medium",
                "description": f"Your {worst_phase[0]} play needs improvement (ACPL: {worst_phase[1]:.1f}). Study {worst_phase[0]} principles."
            })
        
        recommendation_scores = []
        pattern_matches = []
    
    # Check if insight already exists for this period
    existing_insight = db.query(UserInsight).filter(
        UserInsight.user_id == user_id,
        UserInsight.period_start == period_start,
        UserInsight.period_end == period_end,
        UserInsight.analysis_type == analysis_type
    ).first()
    
    if existing_insight:
        # Update existing insight
        existing_insight.total_games = total_games
        existing_insight.games_analyzed = games_analyzed
        existing_insight.average_acpl = average_acpl
        existing_insight.performance_trend = performance_trend
        existing_insight.rating_change = rating_change
        existing_insight.opening_performance = opening_performance
        existing_insight.middlegame_performance = middlegame_performance
        existing_insight.endgame_performance = endgame_performance
        existing_insight.move_quality_stats = move_quality_stats
        existing_insight.frequent_mistakes = frequent_mistakes
        existing_insight.opening_repertoire = opening_stats
        existing_insight.recommendations = recommendations
        # Enhanced recommendation fields
        existing_insight.recommendation_scores = recommendation_scores
        existing_insight.pattern_matches = pattern_matches
    else:
        # Create new insight
        insight = UserInsight(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            analysis_type=analysis_type,
            total_games=total_games,
            games_analyzed=games_analyzed,
            average_acpl=average_acpl,
            performance_trend=performance_trend,
            rating_change=rating_change,
            opening_performance=opening_performance,
            middlegame_performance=middlegame_performance,
            endgame_performance=endgame_performance,
            move_quality_stats=move_quality_stats,
            frequent_mistakes=frequent_mistakes,
            opening_repertoire=opening_stats,
            recommendations=recommendations,
            # Enhanced recommendation fields
            recommendation_scores=recommendation_scores,
            pattern_matches=pattern_matches
        )
        
        db.add(insight)
    
    # Update user's last analysis time
    user.last_analysis_at = datetime.utcnow()
    
    db.commit()


@router.post("/{user_id}/generate")
async def generate_insights(
    user_id: int,
    request: InsightRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate insights for a user."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Calculate period boundaries
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=request.period_days)
    
    # Queue insight generation task
    background_tasks.add_task(
        generate_insights_background,
        user_id,
        period_start,
        period_end,
        request.analysis_type,
        db
    )
    
    return {
        "message": f"Insights generation queued for {request.period_days} day period",
        "period_start": period_start,
        "period_end": period_end
    }


@router.get("/{user_id}", response_model=List[InsightResponse])
async def get_user_insights(
    user_id: int,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get insights for a user."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get insights
    insights = db.query(UserInsight).filter(
        UserInsight.user_id == user_id
    ).order_by(UserInsight.created_at.desc()).offset(skip).limit(limit).all()
    
    return insights


@router.get("/{user_id}/latest")
async def get_latest_insight(user_id: int, db: Session = Depends(get_db)):
    """Get the most recent insight for a user."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get latest insight
    insight = db.query(UserInsight).filter(
        UserInsight.user_id == user_id
    ).order_by(UserInsight.created_at.desc()).first()
    
    if not insight:
        raise HTTPException(status_code=404, detail="No insights found")
    
    return insight


@router.get("/insight/{insight_id}", response_model=InsightResponse)
async def get_insight(insight_id: int, db: Session = Depends(get_db)):
    """Get a specific insight by ID."""
    
    insight = db.query(UserInsight).filter(UserInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    
    return insight


@router.get("/{user_id}/recommendations")
async def get_recommendations(user_id: int, db: Session = Depends(get_db)):
    """Get current recommendations for a user."""
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get latest insight
    insight = db.query(UserInsight).filter(
        UserInsight.user_id == user_id
    ).order_by(UserInsight.period_end.desc()).first()
    
    # Return empty recommendations if no insights yet
    if not insight:
        return {
            "recommendations": [],
            "focus_areas": [],
            "period": None,
            "message": "No insights available yet. Analyze games to get recommendations."
        }
    
    return {
        "recommendations": insight.recommendations or [],
        "focus_areas": insight.focus_areas or [],
        "period": {
            "start": insight.period_start,
            "end": insight.period_end,
            "type": insight.analysis_type
        }
    }


@router.get("/{user_id}/coaching-plan")
async def get_coaching_plan(user_id: int, db: Session = Depends(get_db)):
    """
    Get detailed coaching plan with prioritized recommendations.
    
    Returns enhanced recommendations with actionable steps, priority scores,
    and detected patterns from the latest insight period.
    """
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get latest insight
    insight = db.query(UserInsight).filter(
        UserInsight.user_id == user_id
    ).order_by(UserInsight.period_end.desc()).first()
    
    if not insight:
        raise HTTPException(status_code=404, detail="No insights found. Analyze games first.")
    
    return {
        "recommendations": insight.recommendations or [],
        "priority_scores": insight.recommendation_scores or [],
        "pattern_matches": insight.pattern_matches or [],
        "focus_areas": insight.focus_areas_detailed or {},
        "performance_summary": {
            "average_acpl": insight.average_acpl,
            "performance_trend": insight.performance_trend,
            "rating_change": insight.rating_change,
            "games_analyzed": insight.games_analyzed
        },
        "period": {
            "start": insight.period_start,
            "end": insight.period_end,
            "type": insight.analysis_type
        }
    }


@router.delete("/insight/{insight_id}")
async def delete_insight(insight_id: int, db: Session = Depends(get_db)):
    """Delete a specific insight."""
    
    insight = db.query(UserInsight).filter(UserInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    
    db.delete(insight)
    db.commit()
    
    return {"message": "Insight deleted successfully"}
