"""
Check database contents and trigger Celery analysis on real games
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("=" * 70)
print("DATABASE CHECK & CELERY ANALYSIS TEST")
print("=" * 70)
print()

from app.core.database import SessionLocal
from app.models.game import Game, GameAnalysis
from app.models.user import User

db = SessionLocal()

# Check users
print("Checking users...")
users = db.query(User).all()
print(f"Found {len(users)} user(s)")
for user in users:
    print(f"  - ID: {user.id}, Username: {user.chesscom_username}")

print()

# Check games
print("Checking games...")
games = db.query(Game).all()
print(f"Found {len(games)} game(s)")

games_with_pgn = db.query(Game).filter(Game.pgn.isnot(None)).all()
print(f"Games with PGN: {len(games_with_pgn)}")

analyzed_games = db.query(Game).filter(Game.is_analyzed == True).all()
print(f"Already analyzed: {len(analyzed_games)}")

print()

if not users:
    print("❌ No users in database!")
    print("Please create a user via the frontend first")
    db.close()
    sys.exit(1)

if not games_with_pgn:
    print("❌ No games with PGN data!")
    print("Please fetch games from Chess.com first")
    db.close()
    sys.exit(1)

# Show available games
print("Available games for analysis:")
print()
for i, game in enumerate(games_with_pgn[:10], 1):
    status = "✓ Analyzed" if game.is_analyzed else "○ Not analyzed"
    print(f"{i}. Game ID: {game.id} | {game.white_username} vs {game.black_username} | {status}")

print()

# Ask user which game to analyze
print("=" * 70)
print("READY TO TEST CELERY!")
print("=" * 70)
print()

# Get first unanalyzed game
unanalyzed = [g for g in games_with_pgn if not g.is_analyzed]
if unanalyzed:
    test_game = unanalyzed[0]
    print(f"Selected first unanalyzed game: {test_game.id}")
else:
    test_game = games_with_pgn[0]
    print(f"All games analyzed. Re-analyzing game: {test_game.id}")

print(f"  White: {test_game.white_username}")
print(f"  Black: {test_game.black_username}")
print()

# Import Celery task
from app.tasks.analysis_tasks import analyze_game_task

# Get user
user = db.query(User).filter(User.id == test_game.user_id).first()
if not user:
    user = users[0]

print(f"Queuing analysis task...")
print(f"  Game ID: {test_game.id}")
print(f"  User ID: {user.id}")
print()

# Queue the task
task = analyze_game_task.delay(test_game.id, user.id)

print("✅ TASK QUEUED!")
print(f"   Task ID: {task.id}")
print()
print("=" * 70)
print("NOW CHECK YOUR CELERY WORKER TERMINAL!")
print("=" * 70)
print()
print("You should see logs like:")
print("  🔍 Starting Stockfish analysis for game {game_id}")
print("  🧠 Analyzing game...")
print("  ✅ Game analyzed successfully")
print()
print("The analysis will take 15-30 seconds per game.")
print()

# Monitor for a bit
import time
print("Monitoring task status for 60 seconds...")
print()

for i in range(20):
    status = task.state
    if status == 'PENDING':
        print(f"[{i*3}s] ⏳ Waiting for worker to pick up task...")
    elif status == 'STARTED':
        print(f"[{i*3}s] 🔄 Task is running (analyzing with Stockfish)...")
    elif status == 'SUCCESS':
        print(f"[{i*3}s] ✅ TASK COMPLETED SUCCESSFULLY!")
        print()
        print("Checking database for results...")
        db_check = SessionLocal()
        analysis = db_check.query(GameAnalysis).filter(GameAnalysis.game_id == test_game.id).first()
        if analysis:
            print("✅ Analysis saved to database!")
            print(f"   User ACPL: {analysis.user_acpl}")
            print(f"   Accuracy: {analysis.accuracy_percentage}%")
            print(f"   Blunders: {analysis.blunders}")
            print(f"   Mistakes: {analysis.mistakes}")
        db_check.close()
        break
    elif status == 'FAILURE':
        print(f"[{i*3}s] ❌ Task failed: {task.result}")
        break
    elif status == 'RETRY':
        print(f"[{i*3}s] 🔄 Task retrying after failure...")
    
    time.sleep(3)

print()
print("=" * 70)
print("TEST COMPLETE!")
print("=" * 70)
print()
print("Next steps:")
print("1. Check worker terminal for detailed logs")
print("2. Refresh your frontend to see analysis results")
print("3. You can now analyze more games via the UI!")
print()

db.close()
