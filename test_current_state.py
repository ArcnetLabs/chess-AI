#!/usr/bin/env python3
"""Test current state of backend and data"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

print("=" * 70)
print("🔍 Current Backend State Test")
print("=" * 70)

# 1. Get user
print("\n[1/4] Fetching user gh_wilder...")
user_resp = requests.get(f"{BASE_URL}/users/by-username/gh_wilder")
user = user_resp.json()
print(f"✅ User ID: {user['id']}")
print(f"   Total games: {user.get('total_games', 0)}")
print(f"   Analyzed games: {user.get('analyzed_games', 0)}")

# 2. Get games
print("\n[2/4] Fetching games...")
games_resp = requests.get(f"{BASE_URL}/games/{user['id']}")
games = games_resp.json()
print(f"✅ Games fetched: {len(games)}")
print(f"   Analyzed: {sum(1 for g in games if g.get('is_analyzed'))}")
print(f"   Not analyzed: {sum(1 for g in games if not g.get('is_analyzed'))}")

# 3. Get game stats
print("\n[3/4] Fetching game stats...")
stats_resp = requests.get(f"{BASE_URL}/games/{user['id']}/stats")
stats = stats_resp.json()
print(f"✅ Total games: {stats['total_games']}")
print(f"   Analyzed: {stats['analyzed_games']} ({stats['analysis_percentage']}%)")
print(f"   Wins: {stats['wins']}, Draws: {stats['draws']}, Losses: {stats['losses']}")

# 4. Get analysis summary
print("\n[4/4] Fetching analysis summary...")
try:
    summary_resp = requests.get(f"{BASE_URL}/analysis/{user['id']}/summary?days=7")
    summary = summary_resp.json()
    print(f"✅ Games analyzed (last 7 days): {summary['total_games_analyzed']}")
    if summary['total_games_analyzed'] > 0:
        print(f"   Average ACPL: {summary.get('average_acpl', 'N/A')}")
        print(f"   Move quality categories: {len(summary.get('move_quality_breakdown', {}))}")
    else:
        print("   ⚠️  No analyses yet - this is expected for fresh fetch")
except Exception as e:
    print(f"⚠️  Analysis summary error: {e}")

print("\n" + "=" * 70)
print("📊 SUMMARY")
print("=" * 70)
print(f"✅ Backend: Running on port 8000")
print(f"✅ User: gh_wilder (ID: {user['id']})")
print(f"✅ Games: {len(games)} fetched")
print(f"⚠️  Analyzed: {stats['analyzed_games']} (Need to run analysis)")
print("=" * 70)
