"""In-app notification feed API (P3-PC-02)."""
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import User
from ..services.notifications.notification_service import (
    count_unread,
    list_notifications,
    mark_all_read,
    mark_read,
)

router = APIRouter()


class NotificationItem(BaseModel):
    id: int
    user_id: int
    notification_type: str
    title: str
    body: Optional[str] = None
    payload_json: Optional[Any] = None
    read_at: Optional[datetime] = None
    created_at: datetime
    is_read: bool

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int
    limit: int
    offset: int


class MarkReadResponse(BaseModel):
    success: bool
    notification_id: int


class MarkAllReadResponse(BaseModel):
    marked_count: int


def _to_item(row) -> NotificationItem:
    return NotificationItem(
        id=row.id,
        user_id=row.user_id,
        notification_type=row.notification_type,
        title=row.title,
        body=row.body,
        payload_json=row.payload_json,
        read_at=row.read_at,
        created_at=row.created_at,
        is_read=row.is_read,
    )


@router.get("/{user_id}/notifications", response_model=NotificationListResponse)
async def get_user_notifications(
    user_id: int,
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paginated in-app notification feed with unread count."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rows = list_notifications(
        db, user_id, unread_only=unread_only, limit=limit, offset=offset
    )
    return NotificationListResponse(
        notifications=[_to_item(row) for row in rows],
        unread_count=count_unread(db, user_id),
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{user_id}/notifications/{notification_id}/read",
    response_model=MarkReadResponse,
)
async def mark_notification_read(
    user_id: int,
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not mark_read(db, user_id, notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")

    return MarkReadResponse(success=True, notification_id=notification_id)


@router.post(
    "/{user_id}/notifications/read-all",
    response_model=MarkAllReadResponse,
)
async def mark_all_notifications_read(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark every unread notification as read for the user."""
    require_ownership(current_user, user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    marked = mark_all_read(db, user_id)
    return MarkAllReadResponse(marked_count=marked)
