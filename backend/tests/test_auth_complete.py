"""Complete auth tests with proper async mocking."""
import pytest
from unittest.mock import patch

from app.services.auth.auth_service import auth_service

# auth_service imports get_supabase at module load time; patch where it is used.
_GET_SUPABASE = "app.services.auth.auth_service.get_supabase"


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_up_success(mock_supabase_client):
    """Test successful user registration."""
    with patch(_GET_SUPABASE, return_value=mock_supabase_client):
        result = await auth_service.sign_up(
            email="newuser@example.com",
            password="securepass123",
            metadata={"chesscom_username": "testuser"},
        )

        assert result["success"] is True
        assert result["user"] is not None
        assert result["session"] is not None


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_in_success(mock_supabase_client):
    """Test successful user login."""
    with patch(_GET_SUPABASE, return_value=mock_supabase_client):
        result = await auth_service.sign_in(
            email="test@example.com",
            password="password123",
        )

        assert result["success"] is True
        assert result["user"] is not None
        assert result["session"] is not None
        assert result["access_token"] == "test-access-token-abc123"
        assert result["refresh_token"] == "test-refresh-token-xyz789"


@pytest.mark.auth
@pytest.mark.asyncio
async def test_get_user_with_valid_token(mock_supabase_client):
    """Test getting user with valid token."""
    with patch(_GET_SUPABASE, return_value=mock_supabase_client):
        user = await auth_service.get_user("test-access-token-abc123")

        assert user is not None
        assert user["email"] == "test@example.com"


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_out(mock_supabase_client):
    """Test user sign out."""
    with patch(_GET_SUPABASE, return_value=mock_supabase_client):
        result = await auth_service.sign_out("test-access-token")

        assert isinstance(result, dict)
        assert result["success"] is True
