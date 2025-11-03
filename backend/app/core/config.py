import os
from typing import Any, Dict, List, Optional, Union
from pydantic import AnyHttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings


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
    
    # CORS - Dynamically configured based on environment
    BACKEND_CORS_ORIGINS: List[str] = []
    
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
    
    # Database connection URL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URL", "")
    
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
    STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
    STOCKFISH_DEPTH: int = int(os.getenv("STOCKFISH_DEPTH", "15"))
    STOCKFISH_TIME: float = float(os.getenv("STOCKFISH_TIME", "1.0"))
    
    # OpenAI / OpenRouter API
    OPEN_API_KEY: str = os.getenv("OPEN_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", os.getenv("OPEN_API_KEY", ""))
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    
    # Background Tasks
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    
    # File Storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    REPORTS_DIR: str = os.getenv("REPORTS_DIR", "./reports")
    
    # Analysis Settings
    MAX_GAMES_PER_ANALYSIS: int = 50
    ANALYSIS_CACHE_EXPIRE_HOURS: int = 24
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    model_config = {
        "case_sensitive": True,
        "env_file": "../.env",  # Look in parent directory
        "env_file_encoding": "utf-8"
    }


# Global settings instance
settings = Settings()
