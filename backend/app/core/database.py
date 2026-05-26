from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import redis
from pathlib import Path
from dotenv import load_dotenv

# Load .env file before importing settings
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

from .config import settings


def _validate_database_url(url: str) -> str:
    """Reject missing, SQLite, or non-Postgres URLs outside pytest.

    Production and staging must never silently fall back to SQLite.
    """
    if not url or url == "None":
        raise RuntimeError(
            "DATABASE_URL is not configured. Set DATABASE_URL to a PostgreSQL "
            "connection string (Supabase dashboard or managed Postgres)."
        )

    normalized = url.split(":", 1)[0].lower()
    if normalized == "sqlite":
        if os.getenv("TESTING") == "1":
            return url
        raise RuntimeError(
            "SQLite DATABASE_URL is forbidden outside pytest (TESTING=1). "
            "Configure PostgreSQL via DATABASE_URL — the app must fail fast, "
            "not silently degrade."
        )

    if not url.startswith("postgresql"):
        raise RuntimeError(
            f"Unsupported DATABASE_URL scheme ({normalized!r}). "
            "Only postgresql:// URLs are supported."
        )

    return url


database_url = _validate_database_url(settings.SQLALCHEMY_DATABASE_URI)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5} if database_url.startswith("postgresql") else {},
    echo=settings.LOG_LEVEL == "DEBUG",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Redis (required in production/staging for Celery + cache)
redis_client = None
try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
    )
    redis_client.ping()
except (redis.ConnectionError, redis.TimeoutError, OSError, Exception) as e:
    if settings.ENVIRONMENT in ("production", "staging"):
        raise RuntimeError(
            f"Redis is unreachable at {settings.REDIS_URL} but is required in "
            f"{settings.ENVIRONMENT}. Celery and cache depend on Redis."
        ) from e
    print(f"Warning: Redis not available: {e}. Continuing without Redis (development).")


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
