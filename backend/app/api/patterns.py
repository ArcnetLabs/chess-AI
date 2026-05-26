from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import User
from ..services.patterns.pattern_service import list_user_patterns
from ..tasks.pattern_tasks import detect_patterns_task

router = APIRouter()


class PatternResponse(BaseModel):
    id: int
    user_id: int
    pattern_type: str
    pattern_subtype: str
    severity: str
    confidence_score: float
    occurrence_count: int
    affected_games_count: int
    affected_games_ratio: float
    pattern_description: str
    example_positions: Optional[List[Any]] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    trend_direction: Optional[str] = None
    is_strength: bool = False
    recommended_drill_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PatternAnalyzeResponse(BaseModel):
    task_id: str
    message: str


@router.post("/{user_id}/patterns/analyze", response_model=PatternAnalyzeResponse)
async def trigger_pattern_analysis(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue pattern detection for a user via Celery."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    task = detect_patterns_task.delay(user_id)
    return PatternAnalyzeResponse(
        task_id=task.id,
        message="Pattern detection queued",
    )


@router.get("/{user_id}/patterns", response_model=List[PatternResponse])
async def get_user_patterns(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List persisted patterns for a user."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return list_user_patterns(db, user_id, skip=skip, limit=limit)
