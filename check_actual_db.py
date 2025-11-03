#!/usr/bin/env python3
"""Check which database is actually being used"""

import sys
sys.path.insert(0, 'backend')

from dotenv import load_dotenv
load_dotenv()

from app.core.database import engine, database_url

print("=" * 70)
print("🔍 Actual Database Connection Check")
print("=" * 70)

print(f"\nDatabase URL: {database_url[:60]}...")
print(f"Engine: {engine}")
print(f"Engine URL: {engine.url}")

if "sqlite" in str(engine.url):
    print("\n❌ USING SQLITE IN-MEMORY! Data will be lost on restart!")
elif "supabase" in str(engine.url):
    print("\n✅ USING SUPABASE! Data is persistent!")
elif "postgresql" in str(engine.url):
    print("\n✅ USING POSTGRESQL!")
    if "supabase.co" in str(engine.url):
        print("   ✅ Connected to Supabase!")
    else:
        print("   ⚠️  Connected to local PostgreSQL (not Supabase)")

print("\n" + "=" * 70)
