"""Read-only catalog of a user's semantic memories (redesign P4).

Exposes the coaching-exchange and analysis-pattern slices that ground the
coach, for the "What your coach knows" insights surface. Embeddings are
never returned.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import User
from ..services.coaching.memory_catalog import count_memories, list_memories

router = APIRouter()


class MemoryItem(BaseModel):
    id: int
    content_type: str
    content_text: str
    content_id: Optional[int] = None
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MemoryListResponse(BaseModel):
    memories: List[MemoryItem]
    total_count: int
    limit: int
    offset: int


@router.get("/{user_id}/memories", response_model=MemoryListResponse)
async def get_user_memories(
    user_id: int,
    content_type: Optional[str] = Query(
        None, description="Filter to one slice: 'pattern' or 'coaching'"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the memories that ground this user's coach, newest first."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rows = list_memories(
        db, user_id, content_type=content_type, limit=limit, offset=offset
    )
    return MemoryListResponse(
        memories=[
            MemoryItem(
                id=row.id,
                content_type=row.content_type,
                content_text=row.content_text,
                content_id=row.content_id,
                metadata=row.memory_metadata,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ],
        total_count=count_memories(db, user_id, content_type=content_type),
        limit=limit,
        offset=offset,
    )
