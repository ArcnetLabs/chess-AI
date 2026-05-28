"""Complete API users tests with proper patterns."""
import pytest
from fastapi import Depends, status
from sqlalchemy.orm import Session
from unittest.mock import AsyncMock, patch

from app.__main__ import app
from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User


@pytest.fixture
def api_user(db):
    """Authenticated local user for users API tests."""
    user = User(
        email="api@example.com",
        supabase_user_id="api-user-sub",
        connection_type="username_only",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, api_user):
    """Test client with get_current_user overridden."""
    user_id = api_user.id

    async def override_get_current_user(
        db: Session = Depends(get_db),
    ):
        return db.query(User).filter(User.id == user_id).one()

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.api
def test_create_user_endpoint(authenticated_client, sample_user_data, db):
    """Test user creation endpoint (legacy shim links Chess.com username)."""
    with patch("app.api.users.chesscom_api") as mock_api:
        mock_api.get_player_profile = AsyncMock(
            return_value={
                "username": sample_user_data["chesscom_username"],
                "name": sample_user_data["display_name"],
            }
        )
        mock_api.get_player_stats = AsyncMock(
            return_value={"chess_rapid": {"last": {"rating": 1500}}}
        )

        response = authenticated_client.post("/api/v1/users/", json=sample_user_data)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["chesscom_username"] == sample_user_data["chesscom_username"].lower()


@pytest.mark.api
def test_get_nonexistent_user(authenticated_client, api_user):
    """Foreign user IDs are rejected by ownership check (403, not 404)."""
    response = authenticated_client.get("/api/v1/users/99999")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "own" in response.json()["detail"].lower()


@pytest.mark.api
def test_get_user_by_username_endpoint(
    authenticated_client, sample_user_data, api_user, db
):
    """Test retrieving user by Chess.com username (ownership-scoped)."""
    api_user.chesscom_username = sample_user_data["chesscom_username"].lower()
    db.commit()

    response = authenticated_client.get(
        f"/api/v1/users/by-username/{sample_user_data['chesscom_username']}"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["chesscom_username"] == api_user.chesscom_username
