"""
Live Celery Test - Analyze Real Games
This script tests the Celery task queue with actual games from your database.
"""
import sys
import time
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("=" * 70)
print("LIVE CELERY TEST - REAL GAME ANALYSIS")
print("=" * 70)
print()

# Step 1: Check Redis
print("Step 1: Checking Redis connection...")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.ping()
    print("✅ Redis is connected")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    print("Please start Memurai service")
    sys.exit(1)

print()

# Step 2: Load database and get real games
print("Step 2: Connecting to database and fetching games...")
try:
    from app.core.database import SessionLocal
    from app.models.game import Game
    from app.models.user import User
    
    db = SessionLocal()
    
    # Get first user
    user = db.query(User).first()
    if not user:
        print("❌ No users found in database")
        print("Please create a user first")
        sys.exit(1)
    
    print(f"✅ Found user: {user.chesscom_username} (ID: {user.id})")
    
    # Get games for this user
    games = db.query(Game).filter(
        Game.user_id == user.id,
        Game.pgn.isnot(None)  # Only games with PGN data
    ).limit(5).all()
    
    if not games:
        print("❌ No games with PGN data found")
        print("Please fetch games from Chess.com first")
        sys.exit(1)
    
    print(f"✅ Found {len(games)} games with PGN data")
    print()
    print("Games available for analysis:")
    for i, game in enumerate(games, 1):
        analyzed = "✓ Analyzed" if game.is_analyzed else "○ Not analyzed"
        print(f"   {i}. Game {game.id} - {game.white_username} vs {game.black_username} [{analyzed}]")
    
    db.close()
    
except Exception as e:
    print(f"❌ Database error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Step 3: Import Celery tasks
print("Step 3: Loading Celery tasks...")
try:
    from app.tasks.analysis_tasks import analyze_game_task
    from app.celery_app import celery_app
    
    print("✅ Celery tasks loaded")
    print(f"   Task: {analyze_game_task.name}")
    print(f"   Broker: {celery_app.conf.broker_url}")
    
except Exception as e:
    print(f"❌ Failed to load Celery tasks: {e}")
    sys.exit(1)

print()

# Step 4: Check for active workers
print("Step 4: Checking for Celery workers...")
try:
    inspect = celery_app.control.inspect()
    active_workers = inspect.active()
    
    if active_workers:
        print(f"✅ Found {len(active_workers)} active worker(s)")
        for worker_name in active_workers.keys():
            print(f"   - {worker_name}")
    else:
        print("⚠️  No active workers detected")
        print()
        print("IMPORTANT: You need to start a Celery worker!")
        print("Open a NEW terminal and run:")
        print("   cd e:\\chess\\chess-AI\\backend")
        print("   python start_celery_worker.py")
        print()
        response = input("Have you started the worker? (y/n): ")
        if response.lower() != 'y':
            print("Please start the worker first, then run this script again")
            sys.exit(0)
        
except Exception as e:
    print(f"⚠️  Could not check workers: {e}")
    print("This is normal if no worker is running yet")

print()

# Step 5: Queue a real game for analysis
print("Step 5: Queuing a real game for analysis...")
print()

# Use the first unanalyzed game, or first game if all are analyzed
test_game = None
for game in games:
    if not game.is_analyzed:
        test_game = game
        break

if not test_game:
    test_game = games[0]
    print("⚠️  All games are already analyzed. Re-analyzing first game...")

print(f"Selected game: {test_game.id}")
print(f"   White: {test_game.white_username}")
print(f"   Black: {test_game.black_username}")
print(f"   Time Class: {test_game.time_class}")
print(f"   Already Analyzed: {'Yes' if test_game.is_analyzed else 'No'}")
print()

try:
    # Queue the task
    print("Queuing task to Celery...")
    task = analyze_game_task.delay(test_game.id, user.id)
    
    print(f"✅ Task queued successfully!")
    print(f"   Task ID: {task.id}")
    print(f"   Game ID: {test_game.id}")
    print(f"   User ID: {user.id}")
    print()
    
    # Monitor task status
    print("Monitoring task status...")
    print("(This will check every 3 seconds for up to 2 minutes)")
    print()
    
    max_wait = 120  # 2 minutes
    elapsed = 0
    
    while elapsed < max_wait:
        status = task.state
        
        if status == 'PENDING':
            print(f"[{elapsed}s] ⏳ Task is pending (waiting for worker)...")
        elif status == 'STARTED':
            print(f"[{elapsed}s] 🔄 Task is running (analyzing game)...")
        elif status == 'SUCCESS':
            print(f"[{elapsed}s] ✅ Task completed successfully!")
            print()
            result = task.result
            if isinstance(result, dict):
                print("Analysis Results:")
                print(f"   Status: {result.get('status')}")
                if result.get('status') == 'success':
                    print(f"   User ACPL: {result.get('user_acpl', 'N/A')}")
                    print(f"   Accuracy: {result.get('accuracy', 'N/A')}%")
                    print(f"   Blunders: {result.get('blunders', 'N/A')}")
                    print(f"   Mistakes: {result.get('mistakes', 'N/A')}")
            break
        elif status == 'FAILURE':
            print(f"[{elapsed}s] ❌ Task failed!")
            print(f"   Error: {task.result}")
            break
        elif status == 'RETRY':
            print(f"[{elapsed}s] 🔄 Task is retrying after failure...")
        else:
            print(f"[{elapsed}s] Status: {status}")
        
        time.sleep(3)
        elapsed += 3
    
    if elapsed >= max_wait:
        print()
        print("⏱️  Timeout reached (2 minutes)")
        print("The task is still processing. Check worker logs for progress.")
        print(f"Task ID: {task.id}")
    
except Exception as e:
    print(f"❌ Error queuing task: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Step 6: Verify in database
print("Step 6: Checking database for analysis results...")
try:
    db = SessionLocal()
    from app.models.game import GameAnalysis
    
    analysis = db.query(GameAnalysis).filter(
        GameAnalysis.game_id == test_game.id
    ).first()
    
    if analysis:
        print("✅ Analysis found in database!")
        print(f"   Engine: {analysis.engine_version}")
        print(f"   Depth: {analysis.analysis_depth}")
        print(f"   User ACPL: {analysis.user_acpl}")
        print(f"   Accuracy: {analysis.accuracy_percentage}%")
        print(f"   Blunders: {analysis.blunders}")
        print(f"   Mistakes: {analysis.mistakes}")
        print(f"   Inaccuracies: {analysis.inaccuracies}")
    else:
        print("⚠️  Analysis not yet in database")
        print("Task may still be processing. Check worker logs.")
    
    db.close()
    
except Exception as e:
    print(f"⚠️  Could not check database: {e}")

print()
print("=" * 70)
print("LIVE TEST COMPLETE")
print("=" * 70)
print()
print("What to check:")
print("1. Worker terminal - Should show analysis logs")
print("2. Database - Analysis should be saved")
print("3. Frontend - Refresh to see analysis results")
print()
print("To analyze more games, you can:")
print("- Use the frontend UI (click Analyze button)")
print("- Call the API endpoint directly")
print("- Run this script again")
print()
