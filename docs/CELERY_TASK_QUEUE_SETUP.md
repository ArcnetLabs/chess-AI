# Celery Task Queue Setup Guide

## Overview
This guide explains how to set up and use Celery with Redis for distributed task queue management in the Chess AI application. Celery provides production-grade asynchronous task processing with retry logic, task persistence, and scalability.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Installation & Setup](#installation--setup)
3. [Running Celery Worker](#running-celery-worker)
4. [Task Configuration](#task-configuration)
5. [Usage Examples](#usage-examples)
6. [Monitoring & Management](#monitoring--management)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)

---

## Architecture Overview

### Components

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   FastAPI   │─────▶│    Redis    │◀─────│   Celery    │
│   Backend   │      │   Broker    │      │   Worker    │
└─────────────┘      └─────────────┘      └─────────────┘
      │                                           │
      │                                           │
      └───────────────────┬───────────────────────┘
                          ▼
                  ┌─────────────┐
                  │  PostgreSQL │
                  │  Database   │
                  └─────────────┘
```

### Task Flow

1. **User Request** → FastAPI endpoint receives analysis request
2. **Task Queuing** → Celery task queued to Redis broker
3. **Task Execution** → Celery worker picks up task from queue
4. **Stockfish Analysis** → Worker runs game analysis with Stockfish
5. **Database Update** → Results saved to PostgreSQL
6. **Frontend Polling** → UI polls for completion and updates

---

## Installation & Setup

### Prerequisites

- Python 3.11+
- Redis server running (localhost:6379 or configured URL)
- PostgreSQL database
- Stockfish binary

### 1. Install Dependencies

Dependencies are already in `requirements.txt`:

```txt
redis==5.0.1
celery==5.3.4
```

Install with:
```bash
cd e:\chess\chess-AI\backend
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Update `.env` file:

```env
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration (uses REDIS_URL)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Stockfish Configuration
STOCKFISH_PATH=E:\chess\chess-AI\backend\stockfish\stockfish.exe
STOCKFISH_DEPTH=15
STOCKFISH_TIME=1.0
STOCKFISH_THREADS=2
STOCKFISH_HASH=256
```

### 3. Verify Redis is Running

**Windows:**
```bash
# If using Redis for Windows
redis-server
```

**Docker:**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Check connection:**
```bash
redis-cli ping
# Should return: PONG
```

---

## Running Celery Worker

### Method 1: Using Python Script (Recommended for Windows)

```bash
cd e:\chess\chess-AI\backend
python start_celery_worker.py
```

### Method 2: Using Celery CLI

**Windows (requires solo pool):**
```bash
cd e:\chess\chess-AI\backend
celery -A app.celery_app worker --loglevel=info --pool=solo --concurrency=2 --queues=analysis
```

**Linux/Mac:**
```bash
cd e:\chess\chess-AI\backend
celery -A app.celery_app worker --loglevel=info --concurrency=4 --queues=analysis
```

### Expected Output

```
 -------------- celery@HOSTNAME v5.3.4
--- ***** ----- 
-- ******* ---- Windows-10-10.0.19045-SP0 2026-01-24 14:30:00
- *** --- * --- 
- ** ---------- [config]
- ** ---------- .> app:         chess_ai:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 2 (solo)
-- ******* ---- .> task events: OFF
--- ***** ----- 
 -------------- [queues]
                .> analysis         exchange=analysis(direct) key=analysis

[tasks]
  . app.tasks.analysis_tasks.analyze_batch_games_task
  . app.tasks.analysis_tasks.analyze_game_task

[2026-01-24 14:30:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2026-01-24 14:30:00,000: INFO/MainProcess] mingle: searching for neighbors
[2026-01-24 14:30:01,000: INFO/MainProcess] mingle: all alone
[2026-01-24 14:30:01,000: INFO/MainProcess] celery@HOSTNAME ready.
```

---

## Task Configuration

### Celery App Configuration

**File:** `backend/app/celery_app.py`

Key settings:

```python
celery_app.conf.update(
    # Task execution
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Task routing
    task_routes={
        'app.tasks.analysis_tasks.analyze_game_task': {'queue': 'analysis'},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=50,  # Restart after 50 tasks
    
    # Task limits
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=540,  # 9 minutes soft limit
    
    # Retry settings
    task_acks_late=True,  # Acknowledge after completion
    task_reject_on_worker_lost=True,  # Reject if worker crashes
)
```

### Task Retry Configuration

**File:** `backend/app/tasks/analysis_tasks.py`

```python
@celery_app.task(
    bind=True,
    max_retries=3,  # Retry up to 3 times
    default_retry_delay=60,  # Wait 60 seconds before retry
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True,  # Add randomness to retry delays
)
def analyze_game_task(self, game_id: int, user_id: int):
    # Task implementation
    pass
```

**Retry Schedule:**
- 1st retry: After 60 seconds
- 2nd retry: After ~120 seconds (exponential backoff)
- 3rd retry: After ~240 seconds (exponential backoff)
- Max delay: 600 seconds (10 minutes)

---

## Usage Examples

### Example 1: Analyze Single Game

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/analysis/1/analyze/123
```

**Response:**
```json
{
  "status": "queued",
  "message": "Analysis started",
  "game_id": 123,
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "games_queued": 1
}
```

**Worker Logs:**
```
[2026-01-24 14:30:05,000: INFO] 🔍 [Task a1b2c3d4] Starting Stockfish analysis for game 123
[2026-01-24 14:30:05,100: INFO] 🧠 [Task a1b2c3d4] Analyzing game 123 with UnifiedChessAnalyzer (depth=15)...
[2026-01-24 14:30:25,500: INFO] ✅ [Task a1b2c3d4] Game 123 analyzed successfully: ACPL=45.3, Accuracy=87.5%, Blunders=2, Mistakes=3
```

### Example 2: Analyze Multiple Games

**API Request:**
```bash
curl -X POST http://localhost:8000/api/v1/analysis/1/analyze \
  -H "Content-Type: application/json" \
  -d '{"days": 365, "force_reanalysis": false}'
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

**Worker Logs:**
```
[2026-01-24 14:30:10,000: INFO] 🔍 [Batch Task b2c3d4e5] Queuing 25 games for analysis
[2026-01-24 14:30:10,100: INFO] ✅ [Batch Task b2c3d4e5] Queued 25 analysis tasks
[2026-01-24 14:30:10,200: INFO] 🔍 [Task c3d4e5f6] Starting Stockfish analysis for game 1
[2026-01-24 14:30:10,300: INFO] 🔍 [Task d4e5f6g7] Starting Stockfish analysis for game 2
...
```

### Example 3: Check Task Status (Python)

```python
from app.celery_app import celery_app

# Get task result
task_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
result = celery_app.AsyncResult(task_id)

print(f"Status: {result.state}")
print(f"Result: {result.result}")

# Possible states:
# PENDING - Task waiting to be executed
# STARTED - Task has been started
# SUCCESS - Task completed successfully
# FAILURE - Task failed
# RETRY - Task is being retried
```

---

## Monitoring & Management

### Flower - Web-based Monitoring (Optional)

Install Flower:
```bash
pip install flower
```

Start Flower:
```bash
celery -A app.celery_app flower --port=5555
```

Access dashboard:
```
http://localhost:5555
```

**Features:**
- Real-time task monitoring
- Worker status and statistics
- Task history and results
- Task rate limiting
- Worker pool management

### Redis CLI Monitoring

**Check queue length:**
```bash
redis-cli LLEN celery
```

**View queued tasks:**
```bash
redis-cli LRANGE celery 0 -1
```

**Clear all tasks (DANGER):**
```bash
redis-cli FLUSHDB
```

### Celery CLI Commands

**Inspect active tasks:**
```bash
celery -A app.celery_app inspect active
```

**Inspect registered tasks:**
```bash
celery -A app.celery_app inspect registered
```

**Inspect worker stats:**
```bash
celery -A app.celery_app inspect stats
```

**Purge all tasks:**
```bash
celery -A app.celery_app purge
```

---

## Troubleshooting

### Issue 1: Worker Not Starting

**Error:**
```
Error: No module named 'app'
```

**Solution:**
```bash
# Ensure you're in the backend directory
cd e:\chess\chess-AI\backend

# Set PYTHONPATH
set PYTHONPATH=e:\chess\chess-AI\backend
python start_celery_worker.py
```

### Issue 2: Redis Connection Failed

**Error:**
```
Error: Error 10061 connecting to localhost:6379. No connection could be made
```

**Solution:**
```bash
# Start Redis server
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### Issue 3: Tasks Not Executing

**Symptoms:**
- Tasks queued but not processed
- Worker shows "ready" but no activity

**Debugging:**
```bash
# Check if tasks are in queue
redis-cli LLEN celery

# Check worker is listening to correct queue
celery -A app.celery_app inspect active_queues

# Restart worker with debug logging
celery -A app.celery_app worker --loglevel=debug --pool=solo
```

### Issue 4: Stockfish Not Found

**Error:**
```
FileNotFoundError: Stockfish binary not found
```

**Solution:**
```bash
# Set STOCKFISH_PATH in .env
STOCKFISH_PATH=E:\chess\chess-AI\backend\stockfish\stockfish.exe

# Or let it auto-detect (remove STOCKFISH_PATH from .env)
```

### Issue 5: Task Timeout

**Error:**
```
SoftTimeLimitExceeded: Task exceeded soft time limit (540s)
```

**Solution:**
```python
# Increase time limits in celery_app.py
celery_app.conf.update(
    task_time_limit=1200,  # 20 minutes
    task_soft_time_limit=1080,  # 18 minutes
)
```

---

## Production Deployment

### Docker Compose Configuration

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: chess_ai
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    command: uvicorn app.__main__:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0
      - STOCKFISH_PATH=/app/stockfish/stockfish
    depends_on:
      - redis
      - postgres
    volumes:
      - ./backend:/app

  celery_worker:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info --pool=solo --concurrency=4 --queues=analysis
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0
      - STOCKFISH_PATH=/app/stockfish/stockfish
    depends_on:
      - redis
      - postgres
    volumes:
      - ./backend:/app

  flower:
    build: ./backend
    command: celery -A app.celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  redis_data:
  postgres_data:
```

### Start All Services

```bash
docker-compose up -d
```

### Scale Workers

```bash
# Run 4 worker instances
docker-compose up -d --scale celery_worker=4
```

---

## Performance Tuning

### Worker Concurrency

**Windows (solo pool):**
```bash
# Increase concurrency (tasks per worker)
celery -A app.celery_app worker --pool=solo --concurrency=4
```

**Linux (prefork pool):**
```bash
# Use multiple processes
celery -A app.celery_app worker --pool=prefork --concurrency=8
```

### Task Prioritization

```python
# High priority task
analyze_game_task.apply_async(
    args=[game_id, user_id],
    priority=9  # 0-9, higher = more priority
)

# Low priority task
analyze_game_task.apply_async(
    args=[game_id, user_id],
    priority=1
)
```

### Rate Limiting

```python
# Limit to 10 tasks per minute
@celery_app.task(rate_limit='10/m')
def analyze_game_task(game_id, user_id):
    pass
```

---

## Migration from BackgroundTasks

### Before (FastAPI BackgroundTasks)

```python
@router.post("/analyze/{game_id}")
async def analyze_game(
    game_id: int,
    background_tasks: BackgroundTasks
):
    background_tasks.add_task(analyze_game_func, game_id)
    return {"status": "queued"}
```

**Limitations:**
- ❌ No retry logic
- ❌ Tasks lost on server restart
- ❌ Cannot scale to multiple workers
- ❌ No task monitoring

### After (Celery)

```python
@router.post("/analyze/{game_id}")
async def analyze_game(game_id: int):
    task = analyze_game_task.delay(game_id)
    return {
        "status": "queued",
        "task_id": task.id
    }
```

**Benefits:**
- ✅ Automatic retry with exponential backoff
- ✅ Task persistence (survives restarts)
- ✅ Horizontal scaling (multiple workers)
- ✅ Task monitoring with Flower
- ✅ Task prioritization and rate limiting

---

## Summary

### ✅ What's Implemented

1. **Celery App** (`app/celery_app.py`)
   - Redis broker configuration
   - Task routing and queues
   - Worker settings
   - Retry configuration

2. **Analysis Tasks** (`app/tasks/analysis_tasks.py`)
   - `analyze_game_task` - Single game analysis with retry logic
   - `analyze_batch_games_task` - Batch game analysis
   - Database session management
   - Error handling and logging

3. **API Integration** (`app/api/analysis.py`)
   - Updated endpoints to use Celery tasks
   - Task ID tracking
   - Removed BackgroundTasks dependency

4. **Worker Script** (`start_celery_worker.py`)
   - Windows-compatible worker startup
   - Solo pool configuration
   - Queue configuration

### 🚀 Next Steps

1. **Start Redis** (if not running)
2. **Start Celery Worker** (`python start_celery_worker.py`)
3. **Start FastAPI Backend** (`python -m uvicorn app.__main__:app --reload`)
4. **Test Analysis** (click "Analyze" button in UI)
5. **Monitor Tasks** (check worker logs or use Flower)

### 📊 Monitoring URLs

- **API Documentation**: http://localhost:8000/docs
- **Flower Dashboard**: http://localhost:5555 (if installed)
- **Frontend**: http://localhost:3000

---

## Additional Resources

- [Celery Documentation](https://docs.celeryq.dev/)
- [Redis Documentation](https://redis.io/docs/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Stockfish Integration Guide](./backend/STOCKFISH_INTEGRATION_COMPLETE.md)
