import os
from pathlib import Path
from typing import Annotated, List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file explicitly
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)


class Settings(BaseSettings):
    """Application settings."""
    
    PROJECT_NAME: str = "Chess Insight AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 8)))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Validate SECRET_KEY is properly set."""
        if not v:
            raise ValueError(
                "SECRET_KEY environment variable must be set! "
                "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        if v == "dev-secret-key-change-in-production":
            raise ValueError("Cannot use default SECRET_KEY! Set a secure random key.")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long for security.")
        return v
    
    # CORS - comma-separated in env (Render dashboard), e.g. https://chessrun.netlify.app
    BACKEND_CORS_ORIGINS: Annotated[Union[str, List[str]], NoDecode] = []
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]], info) -> List[str]:
        """Assemble CORS origins with environment-aware defaults."""
        values = info.data if info else {}
        environment = values.get("ENVIRONMENT", "development")
        
        if isinstance(v, str) and not v.startswith("["):
            origins = [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            origins = v
        else:
            origins = []
        
        # Add default development origins if none specified and in dev mode
        if not origins and environment == "development":
            origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
            ]

        # Production fallback when Render env omits BACKEND_CORS_ORIGINS
        if not origins and environment == "production":
            origins = [
                "https://chessrun.netlify.app",
                "http://localhost:3000",
            ]
        
        # Security check: never allow wildcard in production
        if environment == "production" and "*" in origins:
            raise ValueError(
                "Wildcard CORS origin '*' is not allowed in production! "
                "Set BACKEND_CORS_ORIGINS environment variable to specific domains."
            )
        
        return origins
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "chess-insight-files")

    # Project JWT secret (Settings → API → JWT Secret in the Supabase dashboard).
    # Used to verify the HS256 signature on incoming Supabase access tokens
    # WITHOUT a round-trip to Supabase. Required in production; in development
    # an empty value falls back to a slower SDK-based verification path.
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    SUPABASE_JWT_ALGORITHM: str = os.getenv("SUPABASE_JWT_ALGORITHM", "HS256")
    # The "aud" claim in Supabase access tokens is always "authenticated".
    SUPABASE_JWT_AUDIENCE: str = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    
    # Database connection URL
    DATABASE_URL: str = ""
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get database URI from DATABASE_URL."""
        return self.DATABASE_URL or ""
    
    # PostgreSQL individual components (for compatibility)
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    
    # Chess.com API
    CHESSCOM_API_BASE_URL: str = "https://api.chess.com/pub"
    CHESSCOM_API_RATE_LIMIT: int = 100  # requests per minute
    
    # Stockfish Engine
    STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "")  # Auto-detect if empty
    STOCKFISH_DEPTH: int = int(os.getenv("STOCKFISH_DEPTH", "15"))
    STOCKFISH_TIME: float = float(os.getenv("STOCKFISH_TIME", "1.0"))
    STOCKFISH_THREADS: int = int(os.getenv("STOCKFISH_THREADS", "2"))
    STOCKFISH_HASH: int = int(os.getenv("STOCKFISH_HASH", "256"))  # MB
    
    # OpenAI / OpenRouter API
    OPEN_API_KEY: str = os.getenv("OPEN_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", os.getenv("OPEN_API_KEY", ""))
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    # LLM provider routing (coach chat)
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "")
    LLM_PRIMARY_PROVIDER: str = os.getenv(
        "LLM_PRIMARY_PROVIDER", os.getenv("MODEL_PROVIDER", "")
    )
    LLM_LOCAL_BASE_URL: str = os.getenv(
        "LLM_LOCAL_BASE_URL", "http://localhost:8000/v1"
    )
    LLM_LOCAL_MODEL: str = os.getenv("LLM_LOCAL_MODEL", "llama3:8b-instruct")
    LLM_LOCAL_API_KEY: str = os.getenv("LLM_LOCAL_API_KEY", "")
    # A local development model may need longer than a hosted provider for a
    # first response. Keep its output intentionally concise for coach chat.
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "75"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    LLM_COACH_MAX_TOKENS: int = int(os.getenv("LLM_COACH_MAX_TOKENS", "140"))
    LLM_RUNTIME_MODE: str = os.getenv("LLM_RUNTIME_MODE", "production")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "phi3:mini")
    OLLAMA_KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
    OLLAMA_REQUEST_HEADERS_JSON: str = os.getenv(
        "OLLAMA_REQUEST_HEADERS_JSON", ""
    )
    LLM_FALLBACK_CHAIN: str = os.getenv(
        "LLM_FALLBACK_CHAIN", "ollama,local,openrouter,openai"
    )
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL", "google/gemma-2-9b-it:free"
    )
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Background Tasks
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    
    # File Storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "./reports")
    
    # Analysis Settings
    MAX_GAMES_PER_ANALYSIS: int = 50
    ANALYSIS_CACHE_EXPIRE_HOURS: int = 24
    ANALYSIS_JOB_TTL_SECONDS: int = int(
        os.getenv("ANALYSIS_JOB_TTL_SECONDS", str(60 * 60 * 24))
    )
    ANALYSIS_SSE_POLL_INTERVAL_SECONDS: float = float(
        os.getenv("ANALYSIS_SSE_POLL_INTERVAL_SECONDS", "2")
    )
    ANALYSIS_SSE_MAX_POLLS: int = int(
        os.getenv("ANALYSIS_SSE_MAX_POLLS", "300")
    )

    # Scheduled Chess.com sync (P2-AA-05 — optional Celery beat)
    CELERY_BEAT_ENABLED: bool = os.getenv("CELERY_BEAT_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    CHESSCOM_SCHEDULED_SYNC_INTERVAL_MINUTES: int = int(
        os.getenv("CHESSCOM_SCHEDULED_SYNC_INTERVAL_MINUTES", "360")
    )
    CHESSCOM_SCHEDULED_SYNC_DAYS: int = int(
        os.getenv("CHESSCOM_SCHEDULED_SYNC_DAYS", "7")
    )
    CHESSCOM_SCHEDULED_SYNC_MAX_USERS_PER_RUN: int = int(
        os.getenv("CHESSCOM_SCHEDULED_SYNC_MAX_USERS_PER_RUN", "50")
    )
    CHESSCOM_SCHEDULED_SYNC_STAGGER_SECONDS: int = int(
        os.getenv("CHESSCOM_SCHEDULED_SYNC_STAGGER_SECONDS", "2")
    )

    # Weekly summary email stub (P2-RT-02 — optional Celery beat)
    WEEKLY_EMAIL_ENABLED: bool = os.getenv("WEEKLY_EMAIL_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    EMAIL_DELIVERY_ENABLED: bool = os.getenv("EMAIL_DELIVERY_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    EMAIL_FROM_ADDRESS: str = os.getenv("EMAIL_FROM_ADDRESS", "")
    WEEKLY_EMAIL_MAX_USERS_PER_RUN: int = int(
        os.getenv("WEEKLY_EMAIL_MAX_USERS_PER_RUN", "100")
    )
    WEEKLY_EMAIL_STAGGER_SECONDS: int = int(
        os.getenv("WEEKLY_EMAIL_STAGGER_SECONDS", "2")
    )

    # Proactive coaching weekly digest (P3-PC-01 — optional Celery beat)
    WEEKLY_DIGEST_ENABLED: bool = os.getenv("WEEKLY_DIGEST_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    WEEKLY_DIGEST_MAX_USERS_PER_RUN: int = int(
        os.getenv("WEEKLY_DIGEST_MAX_USERS_PER_RUN", "100")
    )
    WEEKLY_DIGEST_STAGGER_SECONDS: int = int(
        os.getenv("WEEKLY_DIGEST_STAGGER_SECONDS", "2")
    )

    # Chat session store (Redis TTL, seconds — default 24h)
    CHAT_SESSION_TTL_SECONDS: int = int(
        os.getenv("CHAT_SESSION_TTL_SECONDS", str(60 * 60 * 24))
    )

    # Semantic memory embeddings (P3-CM-02)
    EMBEDDING_ENABLED: bool = os.getenv("EMBEDDING_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "20"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance
settings = Settings()
