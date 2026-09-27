"""Coaching-memory API: what ChessRun offered, and what happened.

Read-only listing plus an explicit record endpoint. The coach writes through the
record endpoint when it offers a drill or a study; outcomes are computed by the
pattern engine, never posted by a client.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user, require_ownership
from app.models.user import User
from app.services.coaching.interventions import (
    VALID_TYPES,
    coaching_history_summary,
    list_interventions,
    record_intervention,
)

router = APIRouter()


class InterventionCreate(BaseModel):
    intervention_type: str
    pattern_id: Optional[int] = None
    pattern_subtype: Optional[str] = None
    context_signature: Optional[str] = None
    concept: Optional[str] = None
    title: Optional[str] = None
    payload: Optional[dict] = None
    session_id: Optional[str] = None
    offered_at: Optional[datetime] = None


class InterventionResponse(BaseModel):
    id: int
    intervention_type: str
    pattern_id: Optional[int]
    pattern_subtype: Optional[str]
    concept: Optional[str]
    title: Optional[str]
    offered_at: Optional[datetime]
    outcome: str
    outcome_evaluated_at: Optional[datetime]
    outcome_evidence: Optional[dict]

    class Config:
        from_attributes = True


@router.get("/{user_id}/interventions", response_model=List[InterventionResponse])
async def list_user_interventions(
    user_id: int,
    limit: int = 20,
    unresolved_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What the coach has already offered this player, newest first."""
    require_ownership(current_user, user_id)
    return list_interventions(db, user_id, limit=limit, unresolved_only=unresolved_only)


@router.get("/{user_id}/interventions/history")
async def intervention_history(
    user_id: int,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compact history for the profile snapshot and coaching context."""
    require_ownership(current_user, user_id)
    return {"history": coaching_history_summary(db, user_id, limit=limit)}


@router.post("/{user_id}/interventions", response_model=InterventionResponse)
async def create_intervention(
    user_id: int,
    body: InterventionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record an intervention the coach offered.

    Rejects an unknown intervention type rather than storing something the
    outcome machinery cannot interpret.
    """
    require_ownership(current_user, user_id)
    if body.intervention_type not in VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"intervention_type must be one of {list(VALID_TYPES)}",
        )
    return record_intervention(
        db,
        user_id,
        intervention_type=body.intervention_type,
        pattern_id=body.pattern_id,
        pattern_subtype=body.pattern_subtype,
        context_signature=body.context_signature,
        concept=body.concept,
        title=body.title,
        payload=body.payload,
        source="coach",
        session_id=body.session_id,
        offered_at=body.offered_at,
    )
