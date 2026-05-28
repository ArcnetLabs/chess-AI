"""In-app notification feed service (P3-PC-02)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.notification import UserNotification

NOTIFICATION_TYPE_WEEKLY_DIGEST = "weekly_digest"
NOTIFICATION_TYPE_PATTERN_DETECTED = "pattern_detected"
NOTIFICATION_TYPE_TRAINING_MILESTONE = "training_milestone"
NOTIFICATION_TYPE_SYSTEM = "system"


def create_notification(
    db: Session,
    user_id: int,
    notification_type: str,
    title: str,
    *,
    body: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> UserNotification:
    """Persist a new in-app notification for ``user_id``."""
    row = UserNotification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        payload_json=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_notifications(
    db: Session,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> List[UserNotification]:
    """Return notifications for ``user_id``, newest first."""
    query = db.query(UserNotification).filter(UserNotification.user_id == user_id)
    if unread_only:
        query = query.filter(UserNotification.read_at.is_(None))
    return (
        query.order_by(UserNotification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_unread(db: Session, user_id: int) -> int:
    """Count unread notifications for ``user_id``."""
    return (
        db.query(func.count(UserNotification.id))
        .filter(
            UserNotification.user_id == user_id,
            UserNotification.read_at.is_(None),
        )
        .scalar()
    ) or 0


def mark_read(db: Session, user_id: int, notification_id: int) -> bool:
    """
    Mark one notification as read.

    Returns ``False`` when the row is missing or belongs to another user.
    """
    row = (
        db.query(UserNotification)
        .filter(
            UserNotification.id == notification_id,
            UserNotification.user_id == user_id,
        )
        .first()
    )
    if row is None:
        return False
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
    return True


def mark_all_read(db: Session, user_id: int) -> int:
    """Mark every unread notification for ``user_id`` as read. Returns count updated."""
    now = datetime.now(timezone.utc)
    rows = (
        db.query(UserNotification)
        .filter(
            UserNotification.user_id == user_id,
            UserNotification.read_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.read_at = now
    if rows:
        db.commit()
    return len(rows)
