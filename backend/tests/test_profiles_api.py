"""Tests for profile API routes (P1-PP-03)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from app.__main__ import app
from app.middleware.auth_middleware import get_current_user
from app.models.profile import PlayerProfile
from app.models.user import User


@pytest.fixture
def profile_user(db):
    user = User(
        email="profiles@example.com",
        supabase_user_id="profile-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user(db):
    user = User(
        email="other-profile@example.com",
        supabase_user_id="other-profile-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, profile_user):
    async def override_get_current_user():
        return profile_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _create_profile(db, user: User, *, version: int) -> PlayerProfile:
    now = datetime.now(timezone.utc)
    row = PlayerProfile(
        user_id=user.id,
        profile_version=version,
        snapshot_at=now,
        period_start=now,
        period_end=now,
        archetype="Balanced Player",
        primary_strengths=["Solid opening play"],
        primary_weaknesses=["Endgame technique"],
        style_indicators={"aggression": 0.4},
        phase_performance={"opening": 22.0, "middlegame": 28.0, "endgame": 35.0},
        opening_repertoire={"successful": [], "problematic": []},
        tactical_themes=["pins"],
        pattern_summary_refs=[],
        rating_trends={"current": {"rapid": 1500}},
        games_analyzed_count=12,
        patterns_detected_count=2,
        generated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def sample_profile(db, profile_user):
    return _create_profile(db, profile_user, version=1)


@pytest.fixture
def profile_history(db, profile_user):
    return [
        _create_profile(db, profile_user, version=1),
        _create_profile(db, profile_user, version=2),
        _create_profile(db, profile_user, version=3),
    ]


@pytest.mark.api
def test_get_user_profile_returns_latest(
    authenticated_client, profile_user, profile_history
):
    response = authenticated_client.get(
        f"/api/v1/users/{profile_user.id}/profile"
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["profile_version"] == 3
    assert body["user_id"] == profile_user.id
    assert body["archetype"] == "Balanced Player"
    assert body["games_analyzed_count"] == 12


@pytest.mark.api
def test_get_user_profile_not_found(authenticated_client, profile_user):
    response = authenticated_client.get(
        f"/api/v1/users/{profile_user.id}/profile"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "profile" in response.json()["detail"].lower()


@pytest.mark.api
def test_get_profile_history_paginated(
    authenticated_client, profile_user, profile_history
):
    response = authenticated_client.get(
        f"/api/v1/users/{profile_user.id}/profile/history",
        params={"skip": 1, "limit": 2},
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body) == 2
    assert body[0]["profile_version"] == 2
    assert body[1]["profile_version"] == 1


@pytest.mark.api
def test_get_profile_history_empty(authenticated_client, profile_user):
    response = authenticated_client.get(
        f"/api/v1/users/{profile_user.id}/profile/history"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


@pytest.mark.api
def test_trigger_profile_build_queues_celery(authenticated_client, profile_user):
    mock_task = MagicMock()
    mock_task.id = "celery-profile-task-xyz"

    with patch("app.api.profiles.build_profile_task.delay", return_value=mock_task):
        response = authenticated_client.post(
            f"/api/v1/users/{profile_user.id}/profile/build"
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["task_id"] == "celery-profile-task-xyz"
    assert "queued" in body["message"].lower()


@pytest.mark.api
def test_get_profile_forbidden_for_other_user(
    client, profile_user, other_user, sample_profile
):
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.get(f"/api/v1/users/{profile_user.id}/profile")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.api
def test_get_profile_history_forbidden_for_other_user(
    client, profile_user, other_user, sample_profile
):
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.get(
            f"/api/v1/users/{profile_user.id}/profile/history"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.api
def test_trigger_profile_build_forbidden_for_other_user(
    client, profile_user, other_user
):
    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.post(
            f"/api/v1/users/{profile_user.id}/profile/build"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN
