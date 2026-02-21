"""Test the complete analysis flow"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests
import time

# Load .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

print("=" * 70)
print("TESTING COMPLETE ANALYSIS FLOW")
print("=" * 70)

BASE_URL = "http://localhost:8000/api/v1"

# Step 1: Check if backend is running
print("\n1. Checking backend health...")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    if response.status_code == 200:
        health = response.json()
        print(f"   ✅ Backend is healthy")
        print(f"   - Database: {health['checks'].get('database', 'unknown')}")
        print(f"   - Redis: {health['checks'].get('redis', 'unknown')}")
    else:
        print(f"   ❌ Backend returned status {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Backend not reachable: {e}")
    print("   Please start the backend first!")
    sys.exit(1)

# Step 2: Get user and games
print("\n2. Fetching user and games...")
try:
    # Get users
    response = requests.get(f"{BASE_URL}/users/")
    users = response.json()
    
    if not users:
        print("   ❌ No users found. Please create a user first!")
        sys.exit(1)
    
    user = users[0]
    user_id = user['id']
    print(f"   ✅ Found user: {user['chesscom_username']} (ID: {user_id})")
    
    # Get games for this user
    response = requests.get(f"{BASE_URL}/games/{user_id}")
    games = response.json()
    
    if not games:
        print("   ❌ No games found. Please fetch games first!")
        sys.exit(1)
    
    print(f"   ✅ Found {len(games)} games")
    
    # Find an unanalyzed game
    unanalyzed_game = None
    for game in games:
        if not game.get('is_analyzed', False):
            unanalyzed_game = game
            break
    
    if not unanalyzed_game:
        # Use first game anyway
        unanalyzed_game = games[0]
        print(f"   ℹ️  All games analyzed, using game {unanalyzed_game['id']} for re-analysis")
    else:
        print(f"   ✅ Found unanalyzed game: {unanalyzed_game['id']}")
    
    game_id = unanalyzed_game['id']
    
except Exception as e:
    print(f"   ❌ Error fetching data: {e}")
    sys.exit(1)

# Step 3: Check Celery worker status
print("\n3. Checking Celery worker status...")
print("   ℹ️  Make sure Celery worker is running:")
print("   cd e:\\chess\\chess-AI\\backend")
print("   python start_celery_worker.py")
print()
input("   Press Enter when Celery worker is running...")

# Step 4: Queue analysis task
print(f"\n4. Queuing analysis for game {game_id}...")
try:
    response = requests.post(
        f"{BASE_URL}/analysis/{user_id}/analyze/{game_id}",
        params={"force_reanalysis": True}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ Analysis queued successfully!")
        print(f"   - Status: {result.get('status')}")
        print(f"   - Task ID: {result.get('task_id')}")
        print(f"   - Game ID: {result.get('game_id')}")
        task_id = result.get('task_id')
    else:
        print(f"   ❌ Failed to queue analysis: {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)
        
except Exception as e:
    print(f"   ❌ Error queuing analysis: {e}")
    sys.exit(1)

# Step 5: Monitor task execution
print(f"\n5. Monitoring task execution...")
print("   ℹ️  Watch your Celery worker terminal for:")
print("   - Task received message")
print("   - 🔍 Starting Stockfish analysis...")
print("   - 🧠 Analyzing game...")
print("   - ✅ Game analyzed successfully")
print()
print("   Waiting for analysis to complete (max 60 seconds)...")

# Wait and check for analysis completion
max_wait = 60
wait_interval = 3
elapsed = 0

while elapsed < max_wait:
    time.sleep(wait_interval)
    elapsed += wait_interval
    
    # Check if game is analyzed
    try:
        response = requests.get(f"{BASE_URL}/analysis/game/{game_id}")
        if response.status_code == 200:
            analysis = response.json()
            print(f"\n   ✅ ANALYSIS COMPLETE!")
            print(f"   - User ACPL: {analysis.get('user_acpl', 'N/A')}")
            print(f"   - Accuracy: {analysis.get('accuracy_percentage', 'N/A')}%")
            print(f"   - Blunders: {analysis.get('blunders', 0)}")
            print(f"   - Mistakes: {analysis.get('mistakes', 0)}")
            print(f"   - Inaccuracies: {analysis.get('inaccuracies', 0)}")
            print(f"   - Best moves: {analysis.get('best_moves', 0)}")
            break
    except:
        pass
    
    print(f"   ... waiting ({elapsed}s)", end='\r')
else:
    print(f"\n   ⚠️  Analysis not completed within {max_wait} seconds")
    print("   Check Celery worker logs for errors")

# Step 6: Verify in database
print(f"\n6. Verifying data in Supabase...")
try:
    from sqlalchemy import create_engine, text
    
    db_url = os.getenv("DATABASE_URL")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Check game_analyses table
        result = conn.execute(text(
            "SELECT COUNT(*) FROM game_analyses WHERE game_id = :game_id"
        ), {"game_id": game_id})
        count = result.fetchone()[0]
        
        if count > 0:
            print(f"   ✅ Analysis record found in Supabase!")
            
            # Get analysis details
            result = conn.execute(text(
                "SELECT user_acpl, accuracy_percentage, blunders, mistakes FROM game_analyses WHERE game_id = :game_id"
            ), {"game_id": game_id})
            row = result.fetchone()
            print(f"   - ACPL: {row[0]}")
            print(f"   - Accuracy: {row[1]}%")
            print(f"   - Blunders: {row[2]}")
            print(f"   - Mistakes: {row[3]}")
        else:
            print(f"   ❌ No analysis record found in Supabase")
            
except Exception as e:
    print(f"   ⚠️  Could not verify in database: {e}")

print("\n" + "=" * 70)
print("ANALYSIS FLOW TEST COMPLETE")
print("=" * 70)
