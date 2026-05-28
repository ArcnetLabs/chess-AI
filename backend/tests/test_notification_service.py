"""Tests for in-app notification service (P3-PC-02)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.notification import UserNotification
from app.models.user import User
from app.services.notifications.notification_service import (
    NOTIFICATION_TYPE_SYSTEM,
    NOTIFICATION_TYPE_WEEKLY_DIGEST,
    count_unread,
    create_notification,
    list_notifications,
    mark_all_read,
    mark_read,
)


def _create_user(db, suffix: str = "notify") -> User:
    user = User(
        email=f"{suffix}@example.com",
        supabase_user_id=f"{suffix}-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_notification_persists(db):
    user = _create_user(db, "create")

    row = create_notification(
        db,
        user.id,
        NOTIFICATION_TYPE_WEEKLY_DIGEST,
        "Weekly digest ready",
        body="Focus on pins this week.",
        payload={"games_played": 5},
    )

    assert row.id is not None
    assert row.user_id == user.id
    assert row.notification_type == NOTIFICATION_TYPE_WEEKLY_DIGEST
    assert row.title == "Weekly digest ready"
    assert row.body == "Focus on pins this week."
    assert row.payload_json == {"games_played": 5}
    assert row.read_at is None


def test_list_notifications_newest_first_and_unread_filter(db):
    user = _create_user(db, "list")
    base = datetime.now(timezone.utc)

    older = UserNotification(
        user_id=user.id,
        notification_type=NOTIFICATION_TYPE_SYSTEM,
        title="Older",
        created_at=base - timedelta(hours=2),
    )
    newer_unread = UserNotification(
        user_id=user.id,
        notification_type=NOTIFICATION_TYPE_SYSTEM,
        title="Newer unread",
        created_at=base - timedelta(hours=1),
    )
    read_row = UserNotification(
        user_id=user.id,
        notification_type=NOTIFICATION_TYPE_SYSTEM,
        title="Read",
        created_at=base,
        read_at=base,
    )
    db.add_all([older, newer_unread, read_row])
    db.commit()

    all_rows = list_notifications(db, user.id, limit=10)
    assert [r.title for r in all_rows] == ["Read", "Newer unread", "Older"]

    unread_rows = list_notifications(db, user.id, unread_only=True, limit=10)
    assert len(unread_rows) == 2
    assert {r.title for r in unread_rows} == {"Older", "Newer unread"}


def test_count_unread(db):
    user = _create_user(db, "count")
    create_notification(db, user.id, NOTIFICATION_TYPE_SYSTEM, "One")
    row = create_notification(db, user.id, NOTIFICATION_TYPE_SYSTEM, "Two")
    mark_read(db, user.id, row.id)

    assert count_unread(db, user.id) == 1


def test_mark_read_success_and_idempotent(db):
    user = _create_user(db, "mark-one")
    row = create_notification(db, user.id, NOTIFICATION_TYPE_SYSTEM, "Unread")

    assert mark_read(db, user.id, row.id) is True
    db.refresh(row)
    assert row.read_at is not None

    first_read_at = row.read_at
    assert mark_read(db, user.id, row.id) is True
    db.refresh(row)
    assert row.read_at == first_read_at


def test_mark_read_wrong_user_returns_false(db):
    owner = _create_user(db, "owner")
    other = _create_user(db, "other")
    row = create_notification(db, owner.id, NOTIFICATION_TYPE_SYSTEM, "Private")

    assert mark_read(db, other.id, row.id) is False
    db.refresh(row)
    assert row.read_at is None


def test_mark_all_read_returns_count(db):
    user = _create_user(db, "mark-all")
    create_notification(db, user.id, NOTIFICATION_TYPE_SYSTEM, "A")
    create_notification(db, user.id, NOTIFICATION_TYPE_SYSTEM, "B")
    read_row = create_notification(db, user.id, NOTIFICATION_TYPE_SYSTEM, "C")
    mark_read(db, user.id, read_row.id)

    marked = mark_all_read(db, user.id)

    assert marked == 2
    assert count_unread(db, user.id) == 0
