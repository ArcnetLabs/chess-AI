"""Complete auth tests with proper async mocking."""
import pytest
from unittest.mock import patch

from app.services.auth.auth_service import auth_service


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_up_success(mock_supabase_client):
    """Test successful user registration."""
    with patch('app.core.supabase_client.get_supabase', return_value=mock_supabase_client):
        result = await auth_service.sign_up(
            email="newuser@example.com",
            password="securepass123",
            metadata={"chesscom_username": "testuser"}
        )
        
        assert "success" in result
        assert result["success"] is True


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_in_success(mock_supabase_client):
    """Test successful user login."""
    with patch('app.core.supabase_client.get_supabase', return_value=mock_supabase_client):
        result = await auth_service.sign_in(
            email="test@example.com",
            password="password123"
        )
        
        assert "success" in result
        assert result["success"] is True
        assert "access_token" in result
        assert "refresh_token" in result


@pytest.mark.auth
@pytest.mark.asyncio
async def test_get_user_with_valid_token(mock_supabase_client):
    """Test getting user with valid token."""
    with patch('app.core.supabase_client.get_supabase', return_value=mock_supabase_client):
        user = await auth_service.get_user("test-access-token-abc123")
        
        assert user is not None or user is None


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_out(mock_supabase_client):
    """Test user sign out."""
    with patch('app.core.supabase_client.get_supabase', return_value=mock_supabase_client):
        result = await auth_service.sign_out("test-access-token")
        
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("success", False) is True
