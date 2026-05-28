from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import User
from ..services.profiles.profile_service import get_latest_profile, list_profile_history
from ..services.training.training_progress_service import (
    compute_training_progress,
    training_progress_to_dict,
)
from ..tasks.profile_tasks import build_profile_task

router = APIRouter()


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    profile_version: int
    snapshot_at: datetime
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    archetype: Optional[str] = None
    primary_strengths: Optional[List[Any]] = None
    primary_weaknesses: Optional[List[Any]] = None
    style_indicators: Optional[Any] = None
    time_management_profile: Optional[Any] = None
    phase_performance: Optional[Any] = None
    opening_repertoire: Optional[Any] = None
    tactical_themes: Optional[Any] = None
    pattern_summary_refs: Optional[List[Any]] = None
    rating_trends: Optional[Any] = None
    games_analyzed_count: int
    patterns_detected_count: int
    first_game_date: Optional[datetime] = None
    profile_summary: Optional[str] = None
    generated_at: datetime
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    training_progress: Optional[dict] = None

    class Config:
        from_attributes = True


def _profile_response_with_progress(db: Session, user_id: int, profile) -> ProfileResponse:
    """Build profile response with live training progress stats."""
    base = ProfileResponse.model_validate(profile)
    progress = training_progress_to_dict(compute_training_progress(db, user_id))
    return base.model_copy(update={"training_progress": progress})


class ProfileBuildResponse(BaseModel):
    task_id: str
    message: str


@router.get("/{user_id}/profile", response_model=ProfileResponse)
async def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the latest PlayerProfile snapshot for a user."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = get_latest_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile snapshot found")

    return _profile_response_with_progress(db, user_id, profile)


@router.get("/{user_id}/profile/history", response_model=List[ProfileResponse])
async def get_user_profile_history(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List paginated profile snapshots ordered by profile_version descending."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profiles = list_profile_history(db, user_id, skip=skip, limit=limit)
    return [_profile_response_with_progress(db, user_id, row) for row in profiles]


@router.post("/{user_id}/profile/build", response_model=ProfileBuildResponse)
async def trigger_profile_build(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue player profile build for a user via Celery."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    task = build_profile_task.delay(user_id)
    return ProfileBuildResponse(
        task_id=task.id,
        message="Profile build queued",
    )
