from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis
from pathlib import Path
from dotenv import load_dotenv

# Load .env file before importing settings
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

from .config import settings

database_url = settings.SQLALCHEMY_DATABASE_URI

if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not configured. Set DATABASE_URL to a PostgreSQL "
        "connection string (Supabase dashboard or Render Postgres)."
    )

_connect_args = (
    {"connect_timeout": 5}
    if database_url.startswith("postgresql")
    else {}
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
    echo=settings.LOG_LEVEL == "DEBUG",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Redis connection (optional for development)
redis_client = None
try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1
    )
    redis_client.ping()
except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
    print(f"Warning: Redis not available: {e}. Continuing without Redis.")
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
