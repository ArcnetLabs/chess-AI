#!/usr/bin/env python3
"""Check if DATABASE_URL is loaded correctly"""

import os
import sys

# Add backend to path
sys.path.insert(0, 'backend')

# Load .env manually
from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("🔍 Database URL Check")
print("=" * 70)

# Check raw env var
raw_db_url = os.getenv("DATABASE_URL")
print(f"\n1. Raw DATABASE_URL from os.getenv():")
print(f"   {raw_db_url[:60] if raw_db_url else 'NOT SET'}...")

# Check settings
try:
    from app.core.config import settings
    print(f"\n2. Settings.DATABASE_URL:")
    print(f"   {settings.DATABASE_URL[:60] if settings.DATABASE_URL else 'NOT SET'}...")
    
    print(f"\n3. Settings.SQLALCHEMY_DATABASE_URI:")
    print(f"   {settings.SQLALCHEMY_DATABASE_URI[:60] if settings.SQLALCHEMY_DATABASE_URI else 'NOT SET'}...")
    
    if "supabase" in str(settings.DATABASE_URL):
        print("\n✅ DATABASE_URL contains 'supabase' - Should be using Supabase!")
    else:
        print("\n❌ DATABASE_URL does NOT contain 'supabase' - Using SQLite in-memory!")
        
except Exception as e:
    print(f"\n❌ Error loading settings: {e}")

print("\n" + "=" * 70)
