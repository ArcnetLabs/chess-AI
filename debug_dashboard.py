#!/usr/bin/env python3
"""Quick debug script to verify dashboard data flow"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "gh_wilder"

print("=" * 60)
print("🔍 Dashboard Data Flow Debug")
print("=" * 60)

# Step 1: Get user
print("\n[1/4] Fetching user data...")
user_response = requests.get(f"{BASE_URL}/users/by-username/{USERNAME}")
user = user_response.json()
print(f"✅ User ID: {user['id']}")
print(f"   Total games: {user.get('total_games', 0)}")
print(f"   Analyzed games: {user.get('analyzed_games', 0)}")

# Step 2: Get game stats
print("\n[2/4] Fetching game stats...")
stats_response = requests.get(f"{BASE_URL}/games/{user['id']}/stats")
stats = stats_response.json()
print(f"✅ Total games: {stats['total_games']}")
print(f"   Analyzed: {stats['analyzed_games']} ({stats['analysis_percentage']}%)")

# Step 3: Get analysis summary
print("\n[3/4] Fetching analysis summary...")
summary_response = requests.get(f"{BASE_URL}/analysis/{user['id']}/summary?days=7")
summary = summary_response.json()
print(f"✅ Games analyzed (last 7 days): {summary['total_games_analyzed']}")
print(f"   Average ACPL: {summary.get('average_acpl', 'N/A')}")
print(f"   Move quality: {len(summary.get('move_quality_breakdown', {}))} categories")

# Step 4: Get recommendations
print("\n[4/4] Fetching recommendations...")
try:
    recommendations_response = requests.get(f"{BASE_URL}/insights/{user['id']}/recommendations")
    recommendations = recommendations_response.json()
    print(f"✅ Recommendations: {len(recommendations)} found")
    for rec in recommendations[:3]:
        print(f"   - {rec['category']}: {rec['description']}")
except Exception as e:
    print(f"⚠️  No recommendations found: {e}")

print("\n" + "=" * 60)
print("✅ All dashboard data available!")
print("=" * 60)

# Detailed summary data
print("\n📊 Full Analysis Summary:")
print(json.dumps(summary, indent=2))
