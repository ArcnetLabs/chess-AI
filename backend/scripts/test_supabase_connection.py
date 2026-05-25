"""
Test Supabase database connection
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("=" * 70)
print("SUPABASE DATABASE CONNECTION TEST")
print("=" * 70)
print()

# Test 1: Check environment variables
print("Step 1: Checking environment variables...")
from app.core.config import settings

print(f"✓ SUPABASE_URL: {settings.SUPABASE_URL[:30]}...")
print(f"✓ DATABASE_URL configured: {'Yes' if settings.DATABASE_URL else 'No'}")

if not settings.DATABASE_URL or '[YOUR-PASSWORD]' in settings.DATABASE_URL:
    print()
    print("❌ DATABASE_URL not configured properly!")
    print()
    print("Please update your .env file with the actual DATABASE_URL from Supabase:")
    print("1. Go to: https://app.supabase.com/project/ulidwkgufvfyvxllwbqe/settings/database")
    print("2. Copy the Connection String (URI)")
    print("3. Paste it in .env as DATABASE_URL=...")
    print()
    sys.exit(1)

print()

# Test 2: Test database connection
print("Step 2: Testing database connection...")
try:
    from app.core.database import SessionLocal, engine
    from sqlalchemy import text
    
    # Test connection
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"✅ Connected to PostgreSQL!")
        print(f"   Version: {version[:50]}...")
    
except Exception as e:
    print(f"❌ Database connection failed!")
    print(f"   Error: {e}")
    print()
    print("Troubleshooting:")
    print("1. Verify DATABASE_URL in .env is correct")
    print("2. Check your Supabase project is active")
    print("3. Verify database password is correct")
    sys.exit(1)

print()

# Test 3: Check tables
print("Step 3: Checking database tables...")
try:
    from sqlalchemy import inspect
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print(f"✅ Found {len(tables)} table(s):")
    
    expected_tables = ['users', 'games', 'game_analyses', 'user_insights']
    for table in expected_tables:
        if table in tables:
            print(f"   ✓ {table}")
        else:
            print(f"   ✗ {table} (missing)")
    
    if not tables:
        print()
        print("⚠️  No tables found! You may need to run migrations.")
        print("   Run: alembic upgrade head")
    
except Exception as e:
    print(f"⚠️  Could not check tables: {e}")

print()

# Test 4: Check for data
print("Step 4: Checking for existing data...")
try:
    from app.models.user import User
    from app.models.game import Game
    
    db = SessionLocal()
    
    user_count = db.query(User).count()
    game_count = db.query(Game).count()
    
    print(f"✅ Database query successful!")
    print(f"   Users: {user_count}")
    print(f"   Games: {game_count}")
    
    if user_count > 0:
        users = db.query(User).limit(3).all()
        print()
        print("   Sample users:")
        for user in users:
            print(f"   - ID: {user.id}, Username: {user.chesscom_username}")
    
    if game_count > 0:
        games = db.query(Game).limit(3).all()
        print()
        print("   Sample games:")
        for game in games:
            print(f"   - ID: {game.id}, {game.white_username} vs {game.black_username}")
    
    db.close()
    
except Exception as e:
    print(f"⚠️  Could not query data: {e}")

print()
print("=" * 70)
print("CONNECTION TEST COMPLETE!")
print("=" * 70)
print()

if user_count > 0 and game_count > 0:
    print("✅ Your database is connected and has data!")
    print()
    print("You can now test Celery with real games:")
    print("1. Make sure Celery worker is running")
    print("2. Trigger analysis via frontend or API")
    print("3. Watch worker logs for task execution")
else:
    print("⚠️  Database connected but no data found.")
    print()
    print("Next steps:")
    print("1. Create a user via the frontend")
    print("2. Fetch games from Chess.com")
    print("3. Then test Celery analysis")

print()
