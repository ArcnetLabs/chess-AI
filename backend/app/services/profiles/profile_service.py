"""Read-only profile snapshot queries for API routes."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.profile import PlayerProfile


def get_latest_profile(db: Session, user_id: int) -> Optional[PlayerProfile]:
    """Return the newest profile snapshot for a user, or None."""
    return (
        db.query(PlayerProfile)
        .filter(PlayerProfile.user_id == user_id)
        .order_by(PlayerProfile.profile_version.desc())
        .first()
    )


def list_profile_history(
    db: Session,
    user_id: int,
    *,
    skip: int = 0,
    limit: int = 50,
) -> List[PlayerProfile]:
    """Return paginated profile snapshots ordered by version descending."""
    return (
        db.query(PlayerProfile)
        .filter(PlayerProfile.user_id == user_id)
        .order_by(PlayerProfile.profile_version.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
