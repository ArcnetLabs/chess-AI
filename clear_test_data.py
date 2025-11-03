#!/usr/bin/env python3
"""Clear test data from Supabase for fresh start"""

import requests

BASE_URL = "http://localhost:8000/api/v1"
USER_ID = 1

print("🧹 Clearing test data from Supabase...")

# Delete all games for user
try:
    response = requests.delete(f"{BASE_URL}/users/{USER_ID}/games")
    result = response.json()
    print(f"✅ Deleted {result.get('games_deleted', 0)} games")
except Exception as e:
    print(f"⚠️  Error deleting games: {e}")

# Reset user stats
try:
    response = requests.get(f"{BASE_URL}/users/{USER_ID}")
    user = response.json()
    print(f"\n📊 User Stats After Cleanup:")
    print(f"   Total games: {user.get('total_games', 0)}")
    print(f"   Analyzed games: {user.get('analyzed_games', 0)}")
    print(f"   AI analyses used: {user.get('ai_analyses_used', 0)}/5")
except Exception as e:
    print(f"⚠️  Error fetching user: {e}")

print("\n✅ Database cleaned! Ready for fresh testing.")
