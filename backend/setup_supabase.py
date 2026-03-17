"""
Supabase Database Setup and Connection Test
This script will:
1. Test the DATABASE_URL connection
2. Verify tables exist
3. Run migrations if needed
4. Show sample data
"""
import sys
import os
from pathlib import Path

# Ensure we're in the backend directory
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("=" * 80)
print("SUPABASE DATABASE SETUP & CONNECTION TEST")
print("=" * 80)
print()

# Step 1: Load and verify environment variables
print("Step 1: Loading environment variables...")
from dotenv import load_dotenv

env_path = backend_dir.parent / '.env'
load_dotenv(env_path, override=True)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL not found in environment!")
    print(f"   Checked: {env_path}")
    sys.exit(1)

if '[YOUR-PASSWORD]' in db_url:
    print("❌ DATABASE_URL still contains placeholder password!")
    print("   Please update .env with your actual Supabase password")
    sys.exit(1)

if db_url.startswith('postgresql://'):
    print(f"✅ DATABASE_URL configured for PostgreSQL")
    print(f"   Host: {db_url.split('@')[1].split(':')[0] if '@' in db_url else 'unknown'}")
else:
    print(f"❌ DATABASE_URL is not PostgreSQL format: {db_url[:50]}")
    sys.exit(1)

print()

# Step 2: Test direct database connection
print("Step 2: Testing direct PostgreSQL connection...")
try:
    import psycopg2
    from urllib.parse import urlparse
    
    # Parse the DATABASE_URL
    result = urlparse(db_url)
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port
    
    print(f"   Connecting to: {hostname}:{port}/{database}")
    
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port,
        connect_timeout=10
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"✅ Direct connection successful!")
    print(f"   PostgreSQL version: {version[:60]}...")
    
    cursor.close()
    conn.close()
    
except ImportError:
    print("⚠️  psycopg2 not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    print("   Installed! Please run this script again.")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Direct connection failed: {e}")
    print()
    print("Troubleshooting:")
    print("1. Verify your Supabase project is active")
    print("2. Check the password in DATABASE_URL is correct")
    print("3. Ensure your IP is allowed in Supabase (check Network Restrictions)")
    print("4. Try getting a fresh connection string from Supabase dashboard")
    sys.exit(1)

print()

# Step 3: Test SQLAlchemy connection
print("Step 3: Testing SQLAlchemy connection...")
try:
    from sqlalchemy import create_engine, text
    
    engine = create_engine(db_url, pool_pre_ping=True)
    
    with engine.connect() as connection:
        result = connection.execute(text("SELECT current_database(), current_user;"))
        db_name, db_user = result.fetchone()
        print(f"✅ SQLAlchemy connection successful!")
        print(f"   Database: {db_name}")
        print(f"   User: {db_user}")
    
except Exception as e:
    print(f"❌ SQLAlchemy connection failed: {e}")
    sys.exit(1)

print()

# Step 4: Check tables
print("Step 4: Checking database tables...")
try:
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print(f"✅ Found {len(tables)} table(s)")
    
    expected_tables = ['users', 'games', 'game_analyses', 'user_insights']
    missing_tables = []
    
    for table in expected_tables:
        if table in tables:
            print(f"   ✓ {table}")
        else:
            print(f"   ✗ {table} (missing)")
            missing_tables.append(table)
    
    if missing_tables:
        print()
        print("⚠️  Some tables are missing. You need to run migrations.")
        print()
        print("To create tables, run:")
        print("   cd e:\\chess\\chess-AI\\backend")
        print("   alembic upgrade head")
        print()
    
except Exception as e:
    print(f"⚠️  Could not inspect tables: {e}")

print()

# Step 5: Test application configuration
print("Step 5: Testing application configuration...")
try:
    # Force reload of settings with new environment
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    from app.core.config import settings
    
    print(f"✅ Application settings loaded")
    print(f"   DATABASE_URL: {settings.DATABASE_URL[:50]}...")
    print(f"   SQLALCHEMY_DATABASE_URI: {settings.SQLALCHEMY_DATABASE_URI[:50]}...")
    
    if not settings.DATABASE_URL or settings.DATABASE_URL == "":
        print()
        print("❌ WARNING: Application settings show empty DATABASE_URL!")
        print("   This means the backend needs to be restarted to pick up .env changes")
    
except Exception as e:
    print(f"⚠️  Could not load application settings: {e}")

print()

# Step 6: Test database session
print("Step 6: Testing database session...")
try:
    # Force reload database module
    import app.core.database
    importlib.reload(app.core.database)
    from app.core.database import SessionLocal, engine as app_engine
    
    # Check what database the app is using
    db_url_from_app = str(app_engine.url)
    
    if 'sqlite' in db_url_from_app:
        print(f"❌ Application is using SQLite: {db_url_from_app}")
        print()
        print("SOLUTION: Restart your backend application!")
        print("   The backend must be restarted to pick up .env changes")
        print()
        print("Steps:")
        print("   1. Stop the backend (Ctrl+C)")
        print("   2. Run: python -m uvicorn app.__main__:app --reload")
        print()
    elif 'postgresql' in db_url_from_app:
        print(f"✅ Application is using PostgreSQL")
        
        # Try a query
        db = SessionLocal()
        from sqlalchemy import text
        result = db.execute(text("SELECT 1"))
        db.close()
        print(f"✅ Database session works!")
    else:
        print(f"⚠️  Unknown database type: {db_url_from_app}")
    
except Exception as e:
    print(f"⚠️  Session test: {e}")

print()

# Step 7: Check for data
if tables and 'users' in tables and 'games' in tables:
    print("Step 7: Checking for existing data...")
    try:
        from app.models.user import User
        from app.models.game import Game
        
        db = SessionLocal()
        
        user_count = db.query(User).count()
        game_count = db.query(Game).count()
        
        print(f"✅ Data query successful!")
        print(f"   Users: {user_count}")
        print(f"   Games: {game_count}")
        
        if user_count > 0:
            sample_user = db.query(User).first()
            print(f"   Sample user: {sample_user.chesscom_username} (ID: {sample_user.id})")
        
        if game_count > 0:
            sample_game = db.query(Game).first()
            print(f"   Sample game: {sample_game.white_username} vs {sample_game.black_username}")
        
        db.close()
        
    except Exception as e:
        print(f"⚠️  Could not query data: {e}")
        print("   This is normal if tables don't exist yet")

print()
print("=" * 80)
print("SETUP COMPLETE!")
print("=" * 80)
print()

# Summary and next steps
if missing_tables:
    print("⚠️  NEXT STEPS:")
    print("1. Run migrations to create missing tables:")
    print("   cd e:\\chess\\chess-AI\\backend")
    print("   alembic upgrade head")
    print()
    print("2. Restart your backend application")
    print()
elif 'sqlite' in db_url_from_app:
    print("⚠️  NEXT STEPS:")
    print("1. RESTART your backend application to use PostgreSQL:")
    print("   - Stop current backend (Ctrl+C)")
    print("   - Run: python -m uvicorn app.__main__:app --reload")
    print()
else:
    print("✅ DATABASE IS READY!")
    print()
    print("Your Supabase database is connected and working.")
    print()
    print("Next steps:")
    print("1. If backend is running, restart it to ensure it uses PostgreSQL")
    print("2. Create a user via the frontend")
    print("3. Fetch games from Chess.com")
    print("4. Test Celery analysis on real games")
    print()

print("=" * 80)
