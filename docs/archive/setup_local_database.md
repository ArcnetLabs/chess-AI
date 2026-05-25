# Setup Local PostgreSQL - Step by Step

## Step 1: Start Docker Desktop

**Manually start Docker Desktop application on Windows**

Then verify it's running:
```powershell
docker --version
docker ps
```

## Step 2: Start PostgreSQL and Redis

```powershell
cd d:\chess\chess-AI
docker-compose up -d postgres redis
```

Wait for containers to be healthy (~10-30 seconds):
```powershell
docker ps
```

You should see:
- `chess-insight-postgres` (healthy)
- `chess-insight-redis` (up)

## Step 3: Set Environment Variable for Local Database

**Option A: Temporary (current session only)**
```powershell
$env:DATABASE_URL="postgresql://chessai:chessai@localhost:5432/chessai"
```

**Option B: Create .env file**
Create `d:\chess\chess-AI\.env` with:
```
DATABASE_URL=postgresql://chessai:chessai@localhost:5432/chessai
POSTGRES_SERVER=localhost
POSTGRES_USER=chessai
POSTGRES_PASSWORD=chessai
POSTGRES_DB=chessai
POSTGRES_PORT=5432
```

## Step 4: Run Database Migration

```powershell
cd d:\chess\chess-AI\backend
python -m alembic upgrade head
```

## Step 5: Verify Migration

```powershell
docker exec -it chess-insight-postgres psql -U chessai -d chessai -c "\d user_insights"
```

Look for the new columns:
- `recommendation_scores`
- `focus_areas_detailed`
- `pattern_matches`

## Step 6: Start Backend Server

```powershell
cd d:\chess\chess-AI\backend
python -m uvicorn app.__main__:app --reload --host 127.0.0.1 --port 8000
```

## Step 7: Test Enhanced Recommendations

Open a new terminal:

```powershell
# Test health
curl http://localhost:8000/health

# Test new coaching plan endpoint
curl http://localhost:8000/api/insights/1/coaching-plan
```

---

## Quick Start Commands (Copy-Paste)

```powershell
# 1. Start Docker Desktop (manually)

# 2. Start database services
cd d:\chess\chess-AI
docker-compose up -d postgres redis

# 3. Wait for services to be ready (30 seconds)
Start-Sleep -Seconds 30

# 4. Set environment variable
$env:DATABASE_URL="postgresql://chessai:chessai@localhost:5432/chessai"

# 5. Run migration
cd backend
python -m alembic upgrade head

# 6. Start backend
python -m uvicorn app.__main__:app --reload --host 127.0.0.1 --port 8000
```

---

**Once Docker Desktop is running, execute these commands to complete the deployment!**
