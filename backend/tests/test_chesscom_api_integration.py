"""Integration tests for Chess.com API client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.integration.chesscom_api import ChessComAPI, ChessComAPIError


@pytest.mark.asyncio
async def test_get_player_profile_lowercase():
    """Test fetching player profile with lowercase username."""
    api = ChessComAPI()
    
    # Mock the response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "username": "testuser",
        "name": "Test User",
        "status": "premium"
    }
    mock_response.headers = {"content-type": "application/json"}
    mock_response.history = []
    
    with patch.object(api.client, 'get', return_value=mock_response) as mock_get:
        result = await api.get_player_profile("testuser")
        
        assert result["username"] == "testuser"
        assert "name" in result
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_player_profile_mixed_case():
    """Test that mixed case usernames are handled via lowercase conversion."""
    api = ChessComAPI()
    
    # Mock the response (API returns lowercase)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "username": "testuser",
        "name": "Test User"
    }
    mock_response.headers = {"content-type": "application/json"}
    # Simulate redirect history
    redirect_response = MagicMock()
    redirect_response.url = "https://api.chess.com/pub/player/TestUser"
    mock_response.history = [redirect_response]
    mock_response.url = "https://api.chess.com/pub/player/testuser"
    
    with patch.object(api.client, 'get', return_value=mock_response):
        result = await api.get_player_profile("TestUser")
        
        # Should still work because we convert to lowercase
        assert result["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_player_profile_not_found():
    """Test handling of non-existent user."""
    api = ChessComAPI()
    
    # Mock 404 response
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {
        "code": 0,
        "message": "User \"nonexistent\" not found."
    }
    mock_response.text = "Not found"
    
    mock_error = httpx.HTTPStatusError(
        "Not found",
        request=MagicMock(),
        response=mock_response
    )
    
    with patch.object(api.client, 'get', side_effect=mock_error):
        with pytest.raises(ChessComAPIError) as exc_info:
            await api.get_player_profile("nonexistent")
        
        assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_player_profile_rate_limit():
    """Test handling of rate limit (429 response)."""
    api = ChessComAPI()
    
    # Mock 429 response
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.json.return_value = {
        "code": 0,
        "message": "Rate limit exceeded"
    }
    mock_response.text = "Too many requests"
    
    mock_error = httpx.HTTPStatusError(
        "Too many requests",
        request=MagicMock(),
        response=mock_response
    )
    
    with patch.object(api.client, 'get', side_effect=mock_error):
        with pytest.raises(ChessComAPIError) as exc_info:
            await api.get_player_profile("testuser")
        
        assert "rate limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_player_profile_deleted_account():
    """Test handling of deleted/banned account (410 response)."""
    api = ChessComAPI()
    
    # Mock 410 response
    mock_response = MagicMock()
    mock_response.status_code = 410
    mock_response.json.return_value = {
        "code": 0,
        "message": "Account has been closed"
    }
    mock_response.text = "Gone"
    
    mock_error = httpx.HTTPStatusError(
        "Gone",
        request=MagicMock(),
        response=mock_response
    )
    
    with patch.object(api.client, 'get', side_effect=mock_error):
        with pytest.raises(ChessComAPIError) as exc_info:
            await api.get_player_profile("deleteduser")
        
        assert "permanently unavailable" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_client_follows_redirects():
    """Test that the HTTP client is configured to follow redirects."""
    api = ChessComAPI()
    
    # Check client configuration
    assert api.client.follow_redirects is True
    
    # Check User-Agent header
    assert "User-Agent" in api.client.headers
    assert "contact:" in api.client.headers["User-Agent"]


@pytest.mark.asyncio
async def test_get_player_stats():
    """Test fetching player statistics."""
    api = ChessComAPI()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "chess_rapid": {"last": {"rating": 1500}},
        "chess_blitz": {"last": {"rating": 1450}}
    }
    mock_response.headers = {"content-type": "application/json"}
    mock_response.history = []
    
    with patch.object(api.client, 'get', return_value=mock_response):
        result = await api.get_player_stats("testuser")
        
        assert "chess_rapid" in result
        assert "chess_blitz" in result


@pytest.mark.asyncio
async def test_network_error_handling():
    """Test handling of network errors."""
    api = ChessComAPI()
    
    with patch.object(api.client, 'get', side_effect=httpx.ConnectError("Connection failed")):
        with pytest.raises(ChessComAPIError) as exc_info:
            await api.get_player_profile("testuser")
        
        assert "network error" in str(exc_info.value).lower()
