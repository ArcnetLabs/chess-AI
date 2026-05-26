"""Pytest configuration and fixtures for Chess Insight AI."""
import os

# Must be set before importing app (database.py fails fast without DATABASE_URL).
os.environ.setdefault("TESTING", "1")
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///:memory:",
)
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-for-pytest-only-min-32-chars-long",
)
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

import pytest
from typing import Generator
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import Mock, AsyncMock, MagicMock

from app.__main__ import app
from app.core.database import Base, get_db
from app.models.user import User
from app.models.game import Game
from app.models.insights import UserInsight

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db() -> Generator:
    """
    Create a fresh database for each test.
    
    Yields:
        Database session
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db) -> Generator:
    """
    Create a test client with database override.
    
    Args:
        db: Database session fixture
    
    Yields:
        FastAPI test client
    """
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "chesscom_username": "testuser123",
        "email": "test@example.com",
        "display_name": "Test User"
    }


@pytest.fixture
def sample_game_pgn():
    """Sample PGN for testing."""
    return """[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.15"]
[Round "?"]
[White "testuser123"]
[Black "opponent456"]
[Result "1-0"]
[ECO "B20"]
[WhiteElo "1500"]
[BlackElo "1480"]
[TimeControl "600"]
[EndTime "14:23:45 PST"]
[Termination "testuser123 won by checkmate"]

1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 1-0"""


@pytest.fixture
def sample_game_data(sample_game_pgn):
    """Sample game data for testing."""
    return {
        "chesscom_game_id": "12345678",
        "url": "https://chess.com/game/live/12345678",
        "pgn": sample_game_pgn,
        "time_control": "600",
        "time_class": "rapid",
        "rules": "chess",
        "rated": True,
        "white_username": "testuser123",
        "white_rating": 1500,
        "black_username": "opponent456",
        "black_rating": 1480,
        "white_result": "win",
        "black_result": "checkmated",
        "eco": "B20",
        "opening_name": "Sicilian Defense",
        "end_time": "2024-01-15T14:23:45+00:00"
    }


@pytest.fixture
def mock_supabase_client(monkeypatch):
    """Mock Supabase client for testing."""
    class MockSupabaseClient:
        def __init__(self):
            self.auth = MockAuthClient()
        
        def table(self, name):
            return MockTable()
    
    class MockSuccessResponse:
        def __init__(self):
            self.error = None
    
    class MockAuthClient:
        def sign_up(self, credentials):
            return MockAuthResponse(success=True)
        
        def sign_in_with_password(self, credentials):
            return MockAuthResponse(success=True)
        
        def sign_out(self):
            return MockSuccessResponse()
        
        def get_user(self):
            return MockUser()
        
        def set_session(self, access_token, refresh_token):
            pass
        
        def update_user(self, data):
            return MockUser()
        
        def reset_password_email(self, email):
            pass
        
        def refresh_session(self, refresh_token):
            return MockAuthResponse(success=True)
    
    class MockAuthResponse:
        def __init__(self, success=True):
            self.user = MockUser() if success else None
            self.session = MockSession() if success else None
            self.error = None if success else {"message": "Error"}
    
    class MockUser:
        def __init__(self):
            self.id = "test-user-id-123"
            self.email = "test@example.com"
            self.created_at = "2024-01-01T00:00:00Z"
        
        def dict(self):
            return {
                "id": self.id,
                "email": self.email,
                "created_at": self.created_at
            }
    
    class MockSession:
        def __init__(self):
            self.access_token = "test-access-token-abc123"
            self.refresh_token = "test-refresh-token-xyz789"
            self.expires_at = "2024-12-31T23:59:59Z"
    
    class MockTable:
        def __init__(self):
            self._data = []
        
        def select(self, *args):
            return self
        
        def insert(self, data):
            self._data.append(data)
            return self
        
        def update(self, data):
            return self
        
        def delete(self):
            return self
        
        def eq(self, column, value):
            return self
        
        def single(self):
            return self
        
        def execute(self):
            return MockResponse(self._data)
    
    def mock_get_supabase():
        return MockSupabaseClient()
    
    def mock_get_supabase_admin():
        return MockSupabaseClient()
    
    monkeypatch.setattr("app.core.supabase_client.get_supabase", mock_get_supabase)
    monkeypatch.setattr("app.core.supabase_client.get_supabase_admin", mock_get_supabase_admin)
    monkeypatch.setattr("app.services.auth.auth_service.get_supabase", mock_get_supabase)
    monkeypatch.setattr("app.services.auth.auth_service.get_supabase_admin", mock_get_supabase_admin)
    
    return MockSupabaseClient()


@pytest.fixture
def auth_headers():
    """Generate authentication headers for testing."""
    return {"Authorization": "Bearer test-access-token"}
