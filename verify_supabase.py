#!/usr/bin/env python3
"""Verify data is in Supabase by querying directly"""

import psycopg2
import os
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

print("=" * 60)
print("🔍 Supabase Data Verification")
print("=" * 60)

try:
    # Connect to Supabase
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check users
    cursor.execute("SELECT id, chesscom_username, total_games, analyzed_games FROM users")
    users = cursor.fetchall()
    print(f"\n✅ Users in Supabase: {len(users)}")
    for user in users:
        print(f"   - ID: {user[0]}, Username: {user[1]}, Games: {user[2]}, Analyzed: {user[3]}")
    
    # Check games
    cursor.execute("SELECT COUNT(*) FROM games")
    game_count = cursor.fetchone()[0]
    print(f"\n✅ Games in Supabase: {game_count}")
    
    # Check analyses
    cursor.execute("SELECT COUNT(*) FROM game_analyses")
    analysis_count = cursor.fetchone()[0]
    print(f"✅ Analyses in Supabase: {analysis_count}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ Successfully connected to Supabase!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n⚠️  Backend might still be using local PostgreSQL!")
