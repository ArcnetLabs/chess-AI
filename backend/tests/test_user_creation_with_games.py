"""Test user creation with automatic game fetching."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.api.users import create_user, UserCreate
from app.models import User, Game


@pytest.mark.asyncio
async def test_create_user_triggers_background_task():
    """Test that creating a user triggers background game fetching."""
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session
    
    # Mock database session
    mock_db = MagicMock(spec=Session)
    mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing user
    
    # Mock Chess.com API responses
    mock_profile = {
        "username": "testuser",
        "name": "Test User",
        "status": "premium"
    }
    
    mock_stats = {
        "chess_rapid": {"last": {"rating": 1500}}
    }
    
    # Mock background tasks
    mock_bg_tasks = MagicMock(spec=BackgroundTasks)
    
    # Create user data
    user_data = UserCreate(
        chesscom_username="testuser",
        email="test@example.com"
    )
    
    # Mock user for auth
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = 1
    mock_current_user.chesscom_username = None
    mock_current_user.email = None

    # Mock the API calls
    with patch('app.api.users.chesscom_api') as mock_api:
        mock_api.get_player_profile = AsyncMock(return_value=mock_profile)
        mock_api.get_player_stats = AsyncMock(return_value=mock_stats)
        
        # Call create_user
        result = await create_user(
            user_data, mock_bg_tasks, mock_current_user, mock_db
        )
        
        # Verify background task was added
        assert mock_bg_tasks.add_task.called
        
        # Verify the task function is correct
        call_args = mock_bg_tasks.add_task.call_args
        assert call_args[0][0].__name__ == 'fetch_initial_games_background'
        
        # Verify user was committed
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_get_recommendations_returns_empty_for_new_user():
    """Test that recommendations endpoint returns empty array instead of 404."""
    from app.api.insights import get_recommendations
    from sqlalchemy.orm import Session
    
    # Mock database session
    mock_db = MagicMock(spec=Session)
    
    # Mock user exists
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = 1
    
    # Create a mock query chain that returns user, then None for insights
    mock_user_query = MagicMock()
    mock_user_query.filter.return_value.first.return_value = mock_user
    
    mock_insight_query = MagicMock()
    mock_insight_query.filter.return_value.order_by.return_value.first.return_value = None
    
    # Set up query to return different chains
    mock_db.query.side_effect = [mock_user_query, mock_insight_query]
    
    # Call get_recommendations
    result = await get_recommendations(1, mock_current_user, mock_db)
    
    # Should return empty recommendations, not raise 404
    assert result["recommendations"] == []
    assert result["focus_areas"] == []
    assert result["period"] is None
    assert "message" in result


@pytest.mark.asyncio
async def test_user_response_includes_game_count():
    """Test that user response includes total_games field."""
    from app.api.users import get_user
    from sqlalchemy.orm import Session
    
    # Mock database session
    mock_db = MagicMock(spec=Session)
    
    # Mock user
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.chesscom_username = "testuser"

    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = 1
    
    # Mock game count query
    mock_db.query.return_value.filter.side_effect = [
        MagicMock(first=MagicMock(return_value=mock_user)),  # User query
        MagicMock(count=MagicMock(return_value=5))           # Game count query
    ]
    
    # Call get_user
    result = await get_user(1, mock_current_user, mock_db)
    
    # Verify game count was added
    assert hasattr(result, 'total_games')
    assert result.total_games == 5
