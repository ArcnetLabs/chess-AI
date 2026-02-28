"""
Check environment variable loading
"""
import os
from pathlib import Path

# Load .env file manually
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
print(f"Loading .env from: {env_path}")
print(f".env exists: {env_path.exists()}")
print()

load_dotenv(env_path)

print("Environment Variables Check:")
print("=" * 70)

# Check DATABASE_URL
db_url = os.getenv("DATABASE_URL")
print(f"DATABASE_URL: {db_url[:50] if db_url else 'NOT SET'}...")

# Check if it's the placeholder
if db_url and '[YOUR-PASSWORD]' in db_url:
    print("❌ DATABASE_URL still has placeholder password!")
elif db_url and db_url.startswith('postgresql://'):
    print("✅ DATABASE_URL is configured for PostgreSQL")
elif db_url and db_url.startswith('sqlite://'):
    print("⚠️  DATABASE_URL is set to SQLite")
elif not db_url:
    print("❌ DATABASE_URL is not set!")
else:
    print(f"⚠️  DATABASE_URL format: {db_url[:30]}...")

print()

# Check other important vars
print("Other Configuration:")
print(f"REDIS_URL: {os.getenv('REDIS_URL')}")
print(f"CELERY_BROKER_URL: {os.getenv('CELERY_BROKER_URL')}")
print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL')[:30] if os.getenv('SUPABASE_URL') else 'NOT SET'}...")

print()
print("=" * 70)

# Now check what the app sees
print()
print("What the application sees:")
print("=" * 70)

from app.core.config import settings

print(f"settings.DATABASE_URL: {settings.DATABASE_URL[:50] if settings.DATABASE_URL else 'EMPTY'}...")
print(f"settings.SQLALCHEMY_DATABASE_URI: {settings.SQLALCHEMY_DATABASE_URI[:50] if settings.SQLALCHEMY_DATABASE_URI else 'EMPTY'}...")

print()

if not settings.DATABASE_URL or settings.DATABASE_URL == "":
    print("❌ PROBLEM: Application is not seeing DATABASE_URL!")
    print()
    print("Solution:")
    print("1. Make sure .env file has DATABASE_URL set correctly")
    print("2. Restart the backend application")
    print("3. The backend must be restarted to pick up .env changes")
elif settings.DATABASE_URL.startswith('postgresql://'):
    print("✅ Application is configured for PostgreSQL/Supabase")
else:
    print(f"⚠️  Unexpected DATABASE_URL: {settings.DATABASE_URL[:50]}...")

print()
print("=" * 70)
