"""Tests for in-app notification API (P3-PC-02)."""

import pytest
from fastapi import status

from app.__main__ import app
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.notifications.notification_service import (
    NOTIFICATION_TYPE_SYSTEM,
    create_notification,
)


@pytest.fixture
def notify_user(db):
    user = User(
        email="notify-api@example.com",
        supabase_user_id="notify-api-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user(db):
    user = User(
        email="notify-other@example.com",
        supabase_user_id="notify-other-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, notify_user):
    async def override_get_current_user():
        return notify_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.api
def test_list_notifications_includes_unread_count(authenticated_client, notify_user, db):
    create_notification(db, notify_user.id, NOTIFICATION_TYPE_SYSTEM, "First")
    create_notification(db, notify_user.id, NOTIFICATION_TYPE_SYSTEM, "Second")

    response = authenticated_client.get(
        f"/api/v1/users/{notify_user.id}/notifications",
        params={"limit": 10, "offset": 0},
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["unread_count"] == 2
    assert len(body["notifications"]) == 2
    assert body["notifications"][0]["is_read"] is False
    assert body["limit"] == 10
    assert body["offset"] == 0


@pytest.mark.api
def test_list_notifications_forbidden_for_other_user(
    client, notify_user, other_user, db
):
    create_notification(db, notify_user.id, NOTIFICATION_TYPE_SYSTEM, "Private")

    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.get(
            f"/api/v1/users/{notify_user.id}/notifications"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.api
def test_mark_notification_read(authenticated_client, notify_user, db):
    row = create_notification(
        db, notify_user.id, NOTIFICATION_TYPE_SYSTEM, "Mark me"
    )

    response = authenticated_client.patch(
        f"/api/v1/users/{notify_user.id}/notifications/{row.id}/read"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["notification_id"] == row.id


@pytest.mark.api
def test_mark_notification_read_not_found(authenticated_client, notify_user):
    response = authenticated_client.patch(
        f"/api/v1/users/{notify_user.id}/notifications/99999/read"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.api
def test_mark_all_notifications_read(authenticated_client, notify_user, db):
    create_notification(db, notify_user.id, NOTIFICATION_TYPE_SYSTEM, "A")
    create_notification(db, notify_user.id, NOTIFICATION_TYPE_SYSTEM, "B")

    response = authenticated_client.post(
        f"/api/v1/users/{notify_user.id}/notifications/read-all"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["marked_count"] == 2

    list_response = authenticated_client.get(
        f"/api/v1/users/{notify_user.id}/notifications"
    )
    assert list_response.json()["unread_count"] == 0


@pytest.mark.api
def test_list_notifications_forbidden_wrong_user_id(authenticated_client, notify_user):
    """Non-owned user_id returns 403 before resource lookup (auth pattern)."""
    response = authenticated_client.get("/api/v1/users/99999/notifications")

    assert response.status_code == status.HTTP_403_FORBIDDEN
