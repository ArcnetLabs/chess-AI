# Celery Task Queue - User Manual

## 📖 Overview

This manual explains how to use the Celery task queue system for background game analysis in the Chess AI application. Celery provides reliable, scalable, and persistent task processing with automatic retry logic.

---

## 🎯 What is Celery?

Celery is a distributed task queue that allows you to:
- Run game analysis in the background without blocking the API
- Automatically retry failed analyses (up to 3 attempts)
- Scale analysis processing across multiple workers
- Track task progress and status
- Persist tasks even if the server restarts

---

## 🚀 Quick Start Guide

### Prerequisites

✅ **Redis (Memurai)** - Already installed and running as a Windows service  
✅ **Stockfish Engine** - Located at `e:\chess\chess-AI\backend\stockfish\stockfish.exe`  
✅ **Python Dependencies** - Installed via `requirements.txt`

### Starting the System

#### 1. Start Redis (Memurai)
Redis should already be running as a Windows service. Verify with:
```powershell
Get-Service -Name "Memurai"
```

**Expected output:**
```
Status   Name               DisplayName
------   ----               -----------
Running  Memurai            Memurai
```

If not running, start it:
```powershell
Start-Service -Name "Memurai"
```

#### 2. Start Celery Worker

Open a **new terminal** and run:
```bash
cd e:\chess\chess-AI\backend
python start_celery_worker.py
```

**Expected output:**
```
======================================================================
Starting Celery Worker for Chess AI
======================================================================
Broker: redis://localhost:6379/0
Backend: redis://localhost:6379/0
Queues: analysis
Pool: solo (Windows compatible)
======================================================================

 -------------- celery@YOUR-PC v5.3.4
--- ***** ----- 
-- ******* ---- Windows-10-... 2026-02-13 01:00:00
- *** --- * --- 
- ** ---------- [config]
- ** ---------- .> app:         chess_ai:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 2 (solo)
-- ******* ---- .> task events: ON
--- ***** ----- 
 -------------- [queues]
                .> analysis         exchange=analysis(direct) key=analysis

[tasks]
  . app.tasks.analysis_tasks.analyze_batch_games_task
  . app.tasks.analysis_tasks.analyze_game_task

[2026-02-13 01:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2026-02-13 01:00:00,000: INFO/MainProcess] celery@YOUR-PC ready.
```

✅ **Worker is ready when you see "celery@YOUR-PC ready"**

#### 3. Start FastAPI Backend

Open **another terminal** and run:
```bash
cd e:\chess\chess-AI\backend
python -m uvicorn app.__main__:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

✅ **Backend is ready when you see "Application startup complete"**

---

## 📊 Using the System

### Method 1: Via Frontend UI

1. Open the frontend: `http://localhost:3000`
2. Navigate to your games list
3. Click the **"Analyze"** button on any game
4. Watch the worker terminal for real-time progress logs

### Method 2: Via API (cURL)

#### Analyze a Single Game
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/users/1/games/123/analyze" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "status": "queued",
  "message": "Analysis started",
  "game_id": 123,
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

#### Analyze Multiple Games
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/users/1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "days": 30,
    "force_reanalysis": false
  }'
```

**Response:**
```json
{
  "message": "Queued 25 games for analysis",
  "games_queued": 25,
  "task_id": "b2c3d4e5-f6g7-8901-bcde-f12345678901",
  "analysis_mode": "stockfish-only",
  "uses_ai": false
}
```

### Method 3: Via Python Script

```python
import requests

# Analyze single game
response = requests.post(
    "http://localhost:8000/api/v1/analysis/users/1/games/123/analyze"
)
result = response.json()
print(f"Task ID: {result['task_id']}")
print(f"Status: {result['status']}")
```

---

## 🔍 Monitoring Tasks

### Worker Terminal Logs

The Celery worker terminal shows real-time progress:

```
[2026-02-13 01:05:00,000: INFO] 🔍 [Task a1b2c3d4] Starting Stockfish analysis for game 123
[2026-02-13 01:05:00,100: INFO] 🧠 [Task a1b2c3d4] Analyzing game 123 with UnifiedChessAnalyzer (depth=15)...
[2026-02-13 01:05:25,500: INFO] ✅ [Task a1b2c3d4] Game 123 analyzed successfully: ACPL=45.3, Accuracy=87.5%, Blunders=2, Mistakes=3
```

### Log Symbols Explained

- 🔍 **Task Started** - Analysis has begun
- 🧠 **Analyzing** - Stockfish is processing the game
- ✅ **Success** - Analysis completed successfully
- 🔄 **Retry** - Task failed, retrying (attempt X/3)
- ❌ **Failed** - Task failed after all retry attempts
- 📝 **Updating** - Updating existing analysis
- ✨ **Creating** - Creating new analysis record

### Check Task Status (Python)

```python
from app.celery_app import celery_app

# Get task result
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
result = celery_app.AsyncResult(task_id)

print(f"Status: {result.state}")
# Possible states: PENDING, STARTED, SUCCESS, FAILURE, RETRY

if result.ready():
    print(f"Result: {result.result}")
else:
    print("Task still processing...")
```

### Check Analysis Results (API)

```bash
# Get analysis for a specific game
curl "http://localhost:8000/api/v1/analysis/game/123"
```

**Response:**
```json
{
  "id": 1,
  "game_id": 123,
  "engine_version": "Stockfish 16",
  "analysis_depth": 15,
  "user_color": "white",
  "user_acpl": 45.3,
  "opponent_acpl": 52.1,
  "accuracy_percentage": 87.5,
  "brilliant_moves": 1,
  "great_moves": 3,
  "best_moves": 15,
  "excellent_moves": 8,
  "good_moves": 12,
  "inaccuracies": 5,
  "mistakes": 3,
  "blunders": 2,
  "opening_name": "Italian Game",
  "opening_eco": "C50"
}
```

---

## 🔄 Retry Logic

### How Retries Work

If a task fails (e.g., Stockfish crashes, database timeout), Celery automatically retries:

1. **1st Retry** - After ~60 seconds
2. **2nd Retry** - After ~120 seconds (exponential backoff)
3. **3rd Retry** - After ~240 seconds (exponential backoff)

**Max Delay:** 600 seconds (10 minutes)

### Retry Example in Logs

```
[2026-02-13 01:05:00,000: INFO] 🔍 [Task abc123] Starting analysis for game 456
[2026-02-13 01:05:05,000: ERROR] ❌ [Task abc123] Error: Stockfish timeout
[2026-02-13 01:05:05,100: WARNING] 🔄 [Task abc123] Retrying game 456 (attempt 1/3)
[2026-02-13 01:06:05,000: INFO] 🔍 [Task abc123] Starting analysis for game 456
[2026-02-13 01:06:30,000: INFO] ✅ [Task abc123] Game 456 analyzed successfully
```

### Common Retry Scenarios

- **Stockfish timeout** - Engine takes too long
- **Database connection lost** - Temporary network issue
- **Memory error** - System under heavy load
- **File access error** - Temporary file lock

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```env
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Stockfish Configuration
STOCKFISH_PATH=E:\chess\chess-AI\backend\stockfish\stockfish.exe
STOCKFISH_DEPTH=15
STOCKFISH_TIME=1.0
STOCKFISH_THREADS=2
STOCKFISH_HASH=256
```

### Worker Configuration

Edit `backend/app/celery_app.py` to adjust:

```python
celery_app.conf.update(
    worker_prefetch_multiplier=1,      # Tasks per worker
    worker_max_tasks_per_child=50,    # Restart after N tasks
    task_time_limit=600,               # Hard limit (10 min)
    task_soft_time_limit=540,          # Soft limit (9 min)
)
```

### Scaling Workers

Run multiple workers for faster processing:

**Terminal 1:**
```bash
python start_celery_worker.py
```

**Terminal 2:**
```bash
python start_celery_worker.py
```

Each worker can process 2 tasks concurrently (4 total with 2 workers).

---

## 🐛 Troubleshooting

### Issue 1: Worker Won't Start

**Error:** `redis.exceptions.ConnectionError`

**Solution:**
```powershell
# Check if Memurai is running
Get-Service -Name "Memurai"

# Start if stopped
Start-Service -Name "Memurai"
```

### Issue 2: Tasks Not Processing

**Symptoms:** Tasks queued but not executing

**Solution:**
1. Check worker terminal - is it running?
2. Verify worker is listening to `analysis` queue
3. Check Redis connection:
   ```bash
   python -c "import redis; r = redis.Redis(host='localhost', port=6379); print(r.ping())"
   ```

### Issue 3: Stockfish Not Found

**Error:** `FileNotFoundError: Stockfish binary not found`

**Solution:**
1. Verify Stockfish exists:
   ```bash
   Test-Path "E:\chess\chess-AI\backend\stockfish\stockfish.exe"
   ```
2. Update `.env` with correct path:
   ```env
   STOCKFISH_PATH=E:\chess\chess-AI\backend\stockfish\stockfish.exe
   ```

### Issue 4: Tasks Timing Out

**Error:** `SoftTimeLimitExceeded`

**Solution:** Increase time limits in `celery_app.py`:
```python
task_time_limit=1200,        # 20 minutes
task_soft_time_limit=1080,   # 18 minutes
```

### Issue 5: Worker Crashes

**Solution:**
1. Check worker logs for error details
2. Restart worker: `python start_celery_worker.py`
3. Tasks will automatically retry after restart

---

## 📈 Performance Tips

### 1. Adjust Stockfish Depth

Lower depth = faster analysis, less accurate:
```env
STOCKFISH_DEPTH=10  # Faster (5-10 seconds per game)
STOCKFISH_DEPTH=15  # Balanced (15-30 seconds per game)
STOCKFISH_DEPTH=20  # Slower (30-60 seconds per game)
```

### 2. Increase Worker Concurrency

Edit `start_celery_worker.py`:
```python
'concurrency': 4,  # Process 4 tasks simultaneously
```

**Note:** More concurrency = more CPU/memory usage

### 3. Run Multiple Workers

Start 2-3 worker instances for parallel processing.

### 4. Monitor System Resources

- **CPU:** Stockfish is CPU-intensive
- **Memory:** Each worker uses ~200-500 MB
- **Redis:** Minimal resource usage

---

## 🔒 Security Notes

### Production Deployment

1. **Change Redis Password:**
   ```env
   REDIS_URL=redis://:password@localhost:6379/0
   ```

2. **Use SSL/TLS:**
   ```env
   REDIS_URL=rediss://localhost:6379/0
   ```

3. **Restrict Redis Access:**
   - Bind to localhost only
   - Use firewall rules
   - Enable Redis AUTH

4. **Monitor Task Queue:**
   - Set up alerts for failed tasks
   - Monitor queue length
   - Track worker health

---

## 📚 Advanced Usage

### Task Prioritization

```python
from app.tasks.analysis_tasks import analyze_game_task

# High priority
analyze_game_task.apply_async(
    args=[game_id, user_id],
    priority=9  # 0-9, higher = more priority
)

# Low priority
analyze_game_task.apply_async(
    args=[game_id, user_id],
    priority=1
)
```

### Rate Limiting

Limit tasks per time period:
```python
@celery_app.task(rate_limit='10/m')  # 10 tasks per minute
def analyze_game_task(game_id, user_id):
    pass
```

### Task Callbacks

Execute code after task completion:
```python
from celery import chain

# Chain tasks together
workflow = chain(
    analyze_game_task.s(game_id, user_id),
    send_notification.s(user_id)
)
workflow.apply_async()
```

---

## 🆘 Getting Help

### Check Logs

**Worker logs:** Terminal where worker is running  
**Backend logs:** Terminal where FastAPI is running  
**Redis logs:** Windows Event Viewer (if using Memurai)

### Common Commands

```bash
# Check Celery version
celery --version

# Inspect active tasks
celery -A app.celery_app inspect active

# Inspect registered tasks
celery -A app.celery_app inspect registered

# Purge all tasks (DANGER!)
celery -A app.celery_app purge

# Check worker stats
celery -A app.celery_app inspect stats
```

---

## 📝 Summary

### Key Points

✅ **Reliable** - Automatic retries (3 attempts)  
✅ **Persistent** - Tasks survive server restarts  
✅ **Scalable** - Run multiple workers  
✅ **Monitored** - Real-time logs and status tracking  
✅ **Fast** - Background processing doesn't block API

### Workflow

1. User triggers analysis (UI/API)
2. Task queued to Redis
3. Celery worker picks up task
4. Stockfish analyzes game
5. Results saved to database
6. User sees analysis in UI

### Support

For issues or questions:
- Check troubleshooting section above
- Review worker logs for error details
- Verify all services are running (Redis, Worker, Backend)

---

**Version:** 1.0  
**Last Updated:** February 13, 2026  
**System:** Windows with Memurai (Redis)
