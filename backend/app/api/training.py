"""Training plans and drill API (redesign P6).

CRUD over ``training_plans``/``drill_attempts`` for the redesigned
coaching surfaces: plans authored by the coach or interview flow, ad-hoc
drill saves from coach replies, status transitions, attempt recording, and
progress aggregation. Generation from patterns stays in
``drill_generator_service``; the frontend can trigger it via the patterns
analyze endpoint.
"""
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import User
from ..models.training import DrillAttempt, TrainingPlan
from ..services.training.training_plan_service import (
    DrillNotFoundError,
    InvalidTransitionError,
    create_adhoc_drill,
    create_manual_plan,
    get_active_plan,
    list_plan_drills,
    list_plans,
    record_drill_attempt,
    set_drill_status,
)
from ..services.training.training_progress_service import (
    compute_training_progress,
    training_progress_to_dict,
)

router = APIRouter()


class DrillItem(BaseModel):
    id: int
    training_plan_id: Optional[int] = None
    pattern_id: Optional[int] = None
    drill_type: str
    status: str
    prompt_text: str
    position_fen: Optional[str] = None
    expected_answer: Optional[str] = None
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlanItem(BaseModel):
    id: int
    plan_version: int
    status: str
    title: str
    focus_areas: Optional[List[str]] = None
    focus_pattern_ids: Optional[List[int]] = None
    drill_count: int
    completed_drill_count: int
    source: str
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlanDetailItem(PlanItem):
    drills: List[DrillItem] = []


class PlanListResponse(BaseModel):
    plans: List[PlanItem]


class DrillCreateItem(BaseModel):
    drill_type: str = "puzzle"
    prompt_text: str = Field(..., min_length=1)
    position_fen: Optional[str] = None
    pattern_id: Optional[int] = None
    expected_answer: Optional[str] = None


class PlanCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    drills: List[DrillCreateItem] = Field(..., min_length=1)
    focus_areas: Optional[List[str]] = None
    focus_pattern_ids: Optional[List[int]] = None
    source: str = Field("coach", description="interview | coach | self")


class AdhocDrillRequest(BaseModel):
    drill_type: str = "puzzle"
    prompt_text: str = Field(..., min_length=1)
    position_fen: Optional[str] = None
    pattern_id: Optional[int] = None
    training_plan_id: Optional[int] = None
    expected_answer: Optional[str] = None


class DrillStatusRequest(BaseModel):
    status: str = Field(..., description="in_progress | skipped")


class DrillCompleteRequest(BaseModel):
    user_answer: str = Field(..., min_length=1)
    is_correct: bool
    score: Optional[float] = None


def _plan_detail(db: Session, user_id: int, plan: TrainingPlan) -> PlanDetailItem:
    drills = list_plan_drills(db, user_id, plan.id)
    return PlanDetailItem(
        id=plan.id,
        plan_version=plan.plan_version,
        status=plan.status,
        title=plan.title,
        focus_areas=plan.focus_areas,
        focus_pattern_ids=plan.focus_pattern_ids,
        drill_count=plan.drill_count,
        completed_drill_count=plan.completed_drill_count,
        source=plan.source,
        generated_at=plan.generated_at,
        drills=[DrillItem.model_validate(d) for d in drills],
    )


@router.get("/{user_id}/plans", response_model=PlanListResponse)
async def get_user_plans(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the user's training plans, newest version first."""
    require_ownership(current_user, user_id)
    plans = list_plans(db, user_id)
    return PlanListResponse(
        plans=[PlanItem.model_validate(p) for p in plans]
    )


@router.get("/{user_id}/plans/active", response_model=PlanDetailItem)
async def get_user_active_plan(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The active plan with its drills, or 404 when none is active."""
    require_ownership(current_user, user_id)
    plan = get_active_plan(db, user_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="No active training plan")
    return _plan_detail(db, user_id, plan)


@router.post("/{user_id}/plans", response_model=PlanDetailItem, status_code=201)
async def post_user_plan(
    user_id: int,
    request: PlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an active plan authored by the interview flow, coach, or user."""
    require_ownership(current_user, user_id)
    try:
        plan = create_manual_plan(
            db,
            user_id,
            title=request.title,
            drills=[d.model_dump() for d in request.drills],
            focus_areas=request.focus_areas,
            focus_pattern_ids=request.focus_pattern_ids,
            source=request.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _plan_detail(db, user_id, plan)


@router.post("/{user_id}/drills", response_model=DrillItem, status_code=201)
async def post_user_drill(
    user_id: int,
    request: AdhocDrillRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save an ad-hoc drill ("save this drill" from a coach reply)."""
    require_ownership(current_user, user_id)
    try:
        drill = create_adhoc_drill(
            db,
            user_id,
            drill_type=request.drill_type,
            prompt_text=request.prompt_text,
            position_fen=request.position_fen,
            pattern_id=request.pattern_id,
            training_plan_id=request.training_plan_id,
            expected_answer=request.expected_answer,
            attempt_metadata={"origin": "coach_reply"},
        )
    except (ValueError, DrillNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DrillItem.model_validate(drill)


@router.patch("/{user_id}/drills/{drill_id}", response_model=DrillItem)
async def patch_user_drill(
    user_id: int,
    drill_id: int,
    request: DrillStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transition a drill to in_progress or skipped."""
    require_ownership(current_user, user_id)
    try:
        drill = set_drill_status(db, user_id, drill_id, request.status)
    except DrillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DrillItem.model_validate(drill)


@router.post(
    "/{user_id}/drills/{drill_id}/complete", response_model=DrillItem
)
async def complete_user_drill(
    user_id: int,
    drill_id: int,
    request: DrillCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete a drill with the user's answer; syncs plan counters."""
    require_ownership(current_user, user_id)
    try:
        drill = record_drill_attempt(
            db,
            user_id,
            drill_id,
            user_answer=request.user_answer,
            is_correct=request.is_correct,
            score=request.score,
        )
    except DrillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DrillItem.model_validate(drill)


@router.get("/{user_id}/progress")
async def get_user_training_progress(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated drill completion stats for the user."""
    require_ownership(current_user, user_id)
    return training_progress_to_dict(compute_training_progress(db, user_id))
