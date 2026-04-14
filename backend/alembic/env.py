import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Load .env file before importing settings
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

from app.core.config import settings
from app.core.database import Base
from app.models import *  # Import all models

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_database_url():
    """Get database URL from environment variables or config."""
    from sqlalchemy import create_engine, text
    
    # Try DATABASE_URL first
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Check if PostgreSQL URL is accessible
        if db_url.startswith("postgresql"):
            try:
                # Try to connect
                test_engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
                with test_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                test_engine.dispose()
                print(f"✅ Using PostgreSQL: {db_url.split('@')[1].split('/')[0]}")
                return db_url
            except Exception as e:
                print(f"⚠️ PostgreSQL not accessible: {e}")
                print("📁 Using SQLite for local migration")
                return "sqlite:///./chess_ai.db"
        return db_url
    
    # Fallback to individual components
    if os.getenv("POSTGRES_SERVER"):
        pg_url = f"postgresql://{os.getenv('POSTGRES_USER', 'chessai')}:{os.getenv('POSTGRES_PASSWORD', 'chessai')}@{os.getenv('POSTGRES_SERVER', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'chessai')}"
        try:
            test_engine = create_engine(pg_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            test_engine.dispose()
            print(f"✅ Using PostgreSQL: localhost:5432")
            return pg_url
        except Exception as e:
            print(f"⚠️ PostgreSQL not accessible: {e}")
            print("📁 Using SQLite for local migration")
            return "sqlite:///./chess_ai.db"
    
    # Last resort: use SQLite
    print("📁 Using SQLite for local migration")
    return "sqlite:///./chess_ai.db"

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
