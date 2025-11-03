#!/usr/bin/env python3
"""Check which database the backend is connected to"""

import sys
sys.path.insert(0, 'backend')

from app.core.config import settings

print("=" * 60)
print("🔍 Database Connection Check")
print("=" * 60)
print(f"\nDATABASE_URL: {settings.DATABASE_URL[:50]}...")
print(f"POSTGRES_SERVER: {settings.POSTGRES_SERVER}")
print(f"POSTGRES_DB: {settings.POSTGRES_DB}")
print(f"POSTGRES_USER: {settings.POSTGRES_USER}")

if "supabase" in settings.DATABASE_URL:
    print("\n✅ Connected to SUPABASE!")
else:
    print("\n⚠️  NOT connected to Supabase!")
    
print("=" * 60)
