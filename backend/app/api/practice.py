"""Practice focus API: what to work on, and where to do the work.

ChessRun is the coach. Practice happens on ChessReps and ChessFlow, so this
endpoint is deliberately about *focus* — the situation the player keeps getting
wrong, why, and (only when it genuinely fits) which partner the fix belongs on.
It returns no drill content, because we do not have that integration yet and
inventing it is not an option.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user, require_ownership
from app.models.user import User
from app.services.coaching.practice_focus import (
    DEFAULT_FOCUS_LIMIT,
    PRACTICE_PARTNERS,
    build_practice_focus,
)

router = APIRouter()


class PracticePartnerResponse(BaseModel):
    key: str
    name: str
    focus: str
    status: str
    url: Optional[str] = None


class PracticeFocusItem(BaseModel):
    pattern_id: int
    # Every situation behind this one line of advice. They stay separate rows in
    # the ledger, where outcomes are measured per pattern.
    pattern_ids: List[int]
    situations: int
    focus: str
    why: str
    context: Optional[str] = None
    severity: Optional[str] = None
    trend: Optional[str] = None
    occurrences: int
    opportunities: Optional[int] = None
    partner: Optional[PracticePartnerResponse] = None


class PracticeFocusResponse(BaseModel):
    focus: List[PracticeFocusItem]
    partners: List[PracticePartnerResponse]


@router.get("/{user_id}/practice-focus", response_model=PracticeFocusResponse)
async def get_practice_focus(
    user_id: int,
    limit: int = DEFAULT_FOCUS_LIMIT,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What this player should work on next, with the evidence behind it."""
    require_ownership(current_user, user_id)
    items = build_practice_focus(db, user_id, limit=limit)
    return PracticeFocusResponse(
        focus=[PracticeFocusItem(**item) for item in items],
        partners=[
            PracticePartnerResponse(
                key=p.key, name=p.name, focus=p.focus, status=p.status, url=p.url
            )
            for p in PRACTICE_PARTNERS.values()
        ],
    )
