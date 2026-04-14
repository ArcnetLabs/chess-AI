from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import redis
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file before importing settings
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

from .config import settings

# PostgreSQL/Supabase Database
# Use SQLite file for local development if Supabase not accessible
database_url = str(settings.SQLALCHEMY_DATABASE_URI) if settings.SQLALCHEMY_DATABASE_URI else None

# Try PostgreSQL first, fall back to SQLite file on connection error
if database_url and database_url != "None" and database_url.startswith("postgresql"):
    try:
        # Try to connect to PostgreSQL
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
            echo=settings.LOG_LEVEL == "DEBUG"
        )
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✅ Connected to PostgreSQL: {engine.url.host}")
    except Exception as e:
        # Fall back to local SQLite file
        print(f"⚠️ PostgreSQL connection failed: {e}")
        print("📁 Using local SQLite database: ./chess_ai.db")
        database_url = "sqlite:///./chess_ai.db"
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=settings.LOG_LEVEL == "DEBUG"
        )
else:
    # Use local SQLite file for development
    database_url = "sqlite:///./chess_ai.db"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        echo=settings.LOG_LEVEL == "DEBUG"
    )
    print(f"📁 Using local SQLite database: ./chess_ai.db")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Redis connection (optional for development)
redis_client = None
try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
    # Test connection with timeout
    redis_client.ping()
    print("✅ Redis connected successfully")
except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
    # Redis not available - continue without it for development
    print(f"⚠️ Redis not available: {e}. Continuing without Redis (development mode).")
    redis_client = None


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis():
    """Dependency for getting Redis connection."""
    return redis_client
