# Local PostgreSQL Setup Guide

## Quick Start

### 1. Start PostgreSQL with Docker Compose

```bash
cd d:\chess\chess-AI
docker-compose up -d postgres redis
```

This will start:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`

### 2. Create/Update .env File

Create a `.env` file in the root directory with local PostgreSQL connection:

```bash
# Database - Local PostgreSQL
DATABASE_URL=postgresql://chessai:chessai@localhost:5432/chessai
POSTGRES_SERVER=localhost
POSTGRES_USER=chessai
POSTGRES_PASSWORD=chessai
POSTGRES_DB=chessai
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Security (generate new keys for production)
SECRET_KEY=your-secret-key-here-min-32-chars
JWT_SECRET_KEY=your-jwt-secret-key-here-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=11520

# Environment
ENVIRONMENT=development

# Stockfish (optional - will auto-detect)
STOCKFISH_PATH=
STOCKFISH_DEPTH=15
STOCKFISH_TIME=1.0

# AI APIs (optional)
OPENAI_API_KEY=
OPENROUTER_API_KEY=
```

### 3. Run Database Migration

```bash
cd backend
python -m alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade 0002, add_game_filter_indexes -> 99221b79d5ec, merge_migration_heads
INFO  [alembic.runtime.migration] Running upgrade 99221b79d5ec -> 0003, Add enhanced recommendation fields to user_insights table
```

### 4. Verify Migration

```bash
# Connect to PostgreSQL
docker exec -it chess-insight-postgres psql -U chessai -d chessai

# Check columns
\d user_insights

# Should see:
# - recommendation_scores (jsonb)
# - focus_areas_detailed (jsonb)
# - pattern_matches (jsonb)

# Check index
\di idx_user_insights_user_period

# Exit
\q
```

### 5. Start Backend Server

```bash
cd backend
python -m uvicorn app.__main__:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
✅ Connected to PostgreSQL: localhost
✅ Redis connected successfully
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 6. Test the Implementation

```bash
# Check health
curl http://localhost:8000/health

# Generate insights (requires user with games)
curl -X POST http://localhost:8000/api/insights/1/generate

# Get coaching plan (new endpoint)
curl http://localhost:8000/api/insights/1/coaching-plan
```

---

## Alternative: PostgreSQL Without Docker

If you prefer to install PostgreSQL directly:

### Windows

1. **Download PostgreSQL:**
   - Visit: https://www.postgresql.org/download/windows/
   - Download installer (version 15+)
   - Run installer

2. **During Installation:**
   - Port: 5432
   - Username: postgres
   - Password: (set your password)

3. **Create Database:**
   ```bash
   # Open psql
   psql -U postgres
   
   # Create user and database
   CREATE USER chessai WITH PASSWORD 'chessai';
   CREATE DATABASE chessai OWNER chessai;
   GRANT ALL PRIVILEGES ON DATABASE chessai TO chessai;
   \q
   ```

4. **Update .env:**
   ```
   DATABASE_URL=postgresql://chessai:chessai@localhost:5432/chessai
   ```

5. **Continue with Step 3** (Run Migration)

---

## Troubleshooting

### Issue: Docker not starting

**Check Docker Desktop:**
```bash
docker --version
docker ps
```

**Start Docker Desktop** and try again.

### Issue: Port 5432 already in use

**Check what's using the port:**
```bash
netstat -ano | findstr :5432
```

**Stop existing PostgreSQL:**
- Windows Services → PostgreSQL → Stop
- Or change port in docker-compose.yml

### Issue: Connection refused

**Check PostgreSQL is running:**
```bash
docker ps | findstr postgres
```

**Check logs:**
```bash
docker logs chess-insight-postgres
```

### Issue: Migration fails with "relation already exists"

**Stamp the database:**
```bash
python -m alembic stamp head
```

Then try upgrade again.

---

## Quick Commands Reference

```bash
# Start services
docker-compose up -d postgres redis

# Stop services
docker-compose down

# View logs
docker logs chess-insight-postgres
docker logs chess-insight-redis

# Connect to PostgreSQL
docker exec -it chess-insight-postgres psql -U chessai -d chessai

# Restart services
docker-compose restart postgres redis

# Remove all data (fresh start)
docker-compose down -v
docker-compose up -d postgres redis
```

---

## Next Steps After Setup

1. ✅ PostgreSQL running locally
2. ✅ Migration applied
3. ✅ Backend server started
4. Test enhanced recommendations
5. Verify backward compatibility
6. Begin Phase 2 (Move Recommendation System)

---

**Ready to proceed once PostgreSQL is running!**
