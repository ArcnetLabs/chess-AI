"""Contract tests for GET /analysis/{user_id}/status.

"Nothing is running" is a normal state — a dashboard load, a player between
runs — so the endpoint answers `204 No Content` instead of `404`. The 404 put a
red `GET /analysis/1/status 404` in every healthy page's console (the frontend's
axios interceptor logs every non-401 error) and read as a missing resource in
error monitoring. Both frontend readers — `useAnalysisStatus`, which restores an
active job on mount, and the onboarding reveal — already treat "no job" as
`null`, so the status change removes the noise without changing behaviour.

The real failure modes stay failures: another user's id is refused by the
ownership check (403), and a job that *does* exist still answers 200 with its
body.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import status

from app.__main__ import app
from app.api import analysis as analysis_api
from app.middleware.auth_middleware import get_current_user
from app.models.user import User


@pytest.fixture
def status_user(db):
    user = User(
        email="analysis-status@example.com",
        supabase_user_id="analysis-status-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user(db):
    user = User(
        email="other-status@example.com",
        supabase_user_id="other-status-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, status_user):
    async def override_get_current_user():
        return status_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _patch_store(monkeypatch, job):
    """Give the route a hermetic store instead of the process-wide singleton."""
    store = MagicMock()
    store.get_active_job.return_value = job
    monkeypatch.setattr(analysis_api, "get_analysis_job_store", lambda: store)
    return store


@pytest.mark.api
def test_active_status_without_job_is_no_content(
    authenticated_client, status_user, monkeypatch
):
    _patch_store(monkeypatch, None)

    response = authenticated_client.get(
        f"/api/v1/analysis/{status_user.id}/status"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not response.content


@pytest.mark.api
def test_active_status_with_job_returns_the_job(
    authenticated_client, status_user, monkeypatch
):
    _patch_store(
        monkeypatch,
        {
            "job_id": "job-status-1",
            "user_id": status_user.id,
            "status": "running",
            "source": "manual",
            "total_games": 10,
            "completed_games": 4,
            "failed_games": 0,
            "pending_game_ids": [5, 6],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:01:00+00:00",
        },
    )

    response = authenticated_client.get(
        f"/api/v1/analysis/{status_user.id}/status"
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["job_id"] == "job-status-1"
    assert body["status"] == "running"
    assert body["completed_games"] == 4


@pytest.mark.api
def test_active_status_forbidden_for_other_user(
    client, status_user, other_user, monkeypatch
):
    _patch_store(monkeypatch, None)

    async def override_get_current_user():
        return other_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        response = client.get(f"/api/v1/analysis/{status_user.id}/status")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN
