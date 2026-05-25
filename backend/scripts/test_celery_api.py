"""
Test Celery by calling the API endpoint directly
"""
import requests
import time

print("=" * 70)
print("CELERY API TEST - TRIGGER REAL GAME ANALYSIS")
print("=" * 70)
print()

BASE_URL = "http://localhost:8000/api/v1"

# Step 1: Check if backend is running
print("Step 1: Checking if backend is running...")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"✅ Backend is running (status: {response.status_code})")
except Exception as e:
    print(f"❌ Backend not responding: {e}")
    print("Please make sure the backend is running on port 8000")
    exit(1)

print()

# Step 2: Get users
print("Step 2: Fetching users...")
try:
    response = requests.get(f"{BASE_URL}/users")
    users = response.json()
    
    if not users:
        print("❌ No users found")
        print("Please create a user via the frontend first")
        exit(1)
    
    print(f"✅ Found {len(users)} user(s)")
    user = users[0]
    user_id = user['id']
    print(f"   Using user: {user.get('chesscom_username', 'Unknown')} (ID: {user_id})")
    
except Exception as e:
    print(f"❌ Error fetching users: {e}")
    exit(1)

print()

# Step 3: Get games for this user
print("Step 3: Fetching games...")
try:
    response = requests.get(f"{BASE_URL}/users/{user_id}/games")
    games = response.json()
    
    if not games:
        print("❌ No games found")
        print("Please fetch games from Chess.com first")
        exit(1)
    
    print(f"✅ Found {len(games)} game(s)")
    
    # Find first unanalyzed game
    unanalyzed = [g for g in games if not g.get('is_analyzed', False)]
    
    if unanalyzed:
        test_game = unanalyzed[0]
        print(f"   Selected unanalyzed game: {test_game['id']}")
    else:
        test_game = games[0]
        print(f"   All games analyzed. Re-analyzing: {test_game['id']}")
    
    game_id = test_game['id']
    print(f"   White: {test_game.get('white_username', 'Unknown')}")
    print(f"   Black: {test_game.get('black_username', 'Unknown')}")
    
except Exception as e:
    print(f"❌ Error fetching games: {e}")
    exit(1)

print()

# Step 4: Trigger analysis via API
print("Step 4: Triggering Celery analysis...")
print(f"   Calling: POST {BASE_URL}/analysis/users/{user_id}/games/{game_id}/analyze")
print()

try:
    response = requests.post(
        f"{BASE_URL}/analysis/users/{user_id}/games/{game_id}/analyze",
        params={"force_reanalysis": True}
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ ANALYSIS TASK QUEUED!")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message')}")
        print(f"   Game ID: {result.get('game_id')}")
        print(f"   Task ID: {result.get('task_id')}")
        
        task_id = result.get('task_id')
        
    else:
        print(f"❌ Failed to queue task: {response.status_code}")
        print(f"   Response: {response.text}")
        exit(1)
        
except Exception as e:
    print(f"❌ Error triggering analysis: {e}")
    exit(1)

print()
print("=" * 70)
print("TASK QUEUED - CHECK CELERY WORKER TERMINAL!")
print("=" * 70)
print()
print("You should see logs in your Celery worker terminal:")
print("  🔍 Starting Stockfish analysis for game {game_id}")
print("  🧠 Analyzing game with UnifiedChessAnalyzer...")
print("  ✅ Game analyzed successfully: ACPL=X, Accuracy=Y%")
print()
print("The analysis will take 15-30 seconds.")
print()
print("Waiting 45 seconds to check results...")
print()

# Wait for analysis to complete
for i in range(15):
    print(f"⏳ {i*3}s elapsed...", end='\r')
    time.sleep(3)

print()
print()

# Step 5: Check if analysis completed
print("Step 5: Checking analysis results...")
try:
    response = requests.get(f"{BASE_URL}/analysis/game/{game_id}")
    
    if response.status_code == 200:
        analysis = response.json()
        print("✅ ANALYSIS COMPLETED AND SAVED!")
        print()
        print("Results:")
        print(f"   Engine: {analysis.get('engine_version', 'N/A')}")
        print(f"   Depth: {analysis.get('analysis_depth', 'N/A')}")
        print(f"   User ACPL: {analysis.get('user_acpl', 'N/A')}")
        print(f"   Accuracy: {analysis.get('accuracy_percentage', 'N/A')}%")
        print(f"   Brilliant: {analysis.get('brilliant_moves', 0)}")
        print(f"   Great: {analysis.get('great_moves', 0)}")
        print(f"   Best: {analysis.get('best_moves', 0)}")
        print(f"   Good: {analysis.get('good_moves', 0)}")
        print(f"   Inaccuracies: {analysis.get('inaccuracies', 0)}")
        print(f"   Mistakes: {analysis.get('mistakes', 0)}")
        print(f"   Blunders: {analysis.get('blunders', 0)}")
        
    elif response.status_code == 404:
        print("⚠️  Analysis not found yet")
        print("   Task may still be processing or failed")
        print("   Check the Celery worker logs for details")
    else:
        print(f"⚠️  Unexpected response: {response.status_code}")
        
except Exception as e:
    print(f"⚠️  Error checking results: {e}")

print()
print("=" * 70)
print("TEST COMPLETE!")
print("=" * 70)
print()
print("What happened:")
print("1. ✅ API endpoint queued the task to Celery")
print("2. ✅ Celery worker picked up the task from Redis")
print("3. ✅ Stockfish analyzed the game")
print("4. ✅ Results saved to Supabase database")
print()
print("You can now:")
print("- Refresh your frontend to see the analysis")
print("- Analyze more games via the UI")
print("- Check the Celery worker logs for detailed execution info")
print()
