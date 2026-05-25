"""Simple database connection test"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

print("Testing Supabase Connection")
print("=" * 60)

# Check DATABASE_URL
db_url = os.getenv("DATABASE_URL", "")
print(f"\n1. DATABASE_URL from .env:")
if db_url:
    # Hide password
    if '@' in db_url:
        parts = db_url.split('@')
        user_part = parts[0].split(':')[0]
        print(f"   {user_part}:****@{parts[1]}")
    else:
        print(f"   {db_url[:50]}...")
else:
    print("   NOT SET!")

# Test connection
print(f"\n2. Testing PostgreSQL connection...")
try:
    from sqlalchemy import create_engine, text
    
    if not db_url or '[YOUR-PASSWORD]' in db_url:
        print("   ❌ DATABASE_URL not configured properly")
    else:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
            print(f"   ✅ Connected to database: {db_name}")
            
        # Check tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"\n3. Tables found: {len(tables)}")
        for table in tables[:10]:
            print(f"   - {table}")
            
except Exception as e:
    print(f"   ❌ Connection failed: {str(e)[:100]}")

print("\n" + "=" * 60)
