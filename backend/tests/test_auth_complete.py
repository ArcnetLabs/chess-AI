"""Auth service tests — passwordless magic-link flows."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.auth.auth_service import auth_service

_GET_SUPABASE = "app.services.auth.auth_service.get_supabase"


@pytest.mark.auth
@pytest.mark.asyncio
async def test_send_magic_link_success():
    mock_client = MagicMock()
    mock_client.auth.sign_in_with_otp.return_value = None

    with patch(_GET_SUPABASE, return_value=mock_client):
        result = await auth_service.send_magic_link(
            "newuser@example.com",
            chesscom_username="testuser",
        )

        assert result["success"] is True
        mock_client.auth.sign_in_with_otp.assert_called_once()
        call_args = mock_client.auth.sign_in_with_otp.call_args[0][0]
        assert call_args["email"] == "newuser@example.com"
        assert call_args["options"]["data"]["chesscom_username"] == "testuser"


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_in_delegates_to_magic_link():
    mock_client = MagicMock()
    mock_client.auth.sign_in_with_otp.return_value = None

    with patch(_GET_SUPABASE, return_value=mock_client):
        result = await auth_service.sign_in(
            "test@example.com",
            chesscom_username="player1",
        )

        assert result["success"] is True
        mock_client.auth.sign_in_with_otp.assert_called_once()


@pytest.mark.auth
@pytest.mark.asyncio
async def test_get_user_with_valid_token(mock_supabase_client):
    with patch(_GET_SUPABASE, return_value=mock_supabase_client):
        user = await auth_service.get_user("test-access-token-abc123")

        assert user is not None
        assert user["email"] == "test@example.com"


@pytest.mark.auth
@pytest.mark.asyncio
async def test_sign_out(mock_supabase_client):
    with patch(_GET_SUPABASE, return_value=mock_supabase_client):
        result = await auth_service.sign_out("test-access-token")

        assert isinstance(result, dict)
        assert result["success"] is True
