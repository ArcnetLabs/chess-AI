# 🚀 Chess Insight AI - Complete Setup Guide

A comprehensive AI-powered chess analysis platform that helps Chess.com players understand their performance, identify weaknesses, and improve their game through detailed insights and recommendations.

---

## 📋 Table of Contents

- [Application Capabilities](#-application-capabilities)
- [System Requirements](#-system-requirements)
- [Deployment Architecture](#-deployment-architecture)
- [Installation Guide](#-installation-guide)
- [Configuration](#-configuration)
- [Running the Application](#-running-the-application)
- [Troubleshooting](#-troubleshooting)
- [API Documentation](#-api-documentation)

---

## 🎯 Application Capabilities

### Core Features

#### 1. **Chess.com Integration**
- Connect with Chess.com username
- Automatic game fetching from Chess.com API
- Support for all time controls (Blitz, Rapid, Bullet, Daily)
- Smart filtering by date range, rating, and game type
- **Redis caching** - 1-hour cache for game archives (95% faster on cache hits)
- **Rate limiting** - 50 requests per minute per user to prevent API abuse

#### 2. **Advanced Game Analysis**
- **Stockfish 16 Engine** - Deep position evaluation
- **Unified Analysis System** - Combines Stockfish + optional AI insights
- **Performance Metrics:**
  - ACPL (Average Centipawn Loss)
  - Accuracy percentage
  - Blunders, mistakes, inaccuracies count
  - Best moves, excellent moves, good moves
  - Opening phase, middlegame, endgame performance
  - Time management analysis
  - Critical moments identification

#### 3. **Background Processing**
- **Celery Task Queue** - Asynchronous game analysis
- **Redis Broker** - Fast, reliable task distribution
- **Retry Logic** - Automatic retry on failures (max 3 attempts)
- **Progress Tracking** - Real-time task status monitoring
- Analyze single games or batch process multiple games

#### 4. **Performance Insights**
- Rating trend analysis
- Win/loss/draw statistics
- Performance by time control
- Opening repertoire analysis
- Opponent strength analysis
- Phase-based performance (opening/middlegame/endgame)
- Personalized recommendations

#### 5. **Visual Dashboard**
- Modern, responsive UI built with Next.js 14
- Interactive charts (Recharts)
- Game history timeline
- Performance metrics visualization
- Analysis results display
- User-friendly error messages

#### 6. **Data Management**
- **Supabase PostgreSQL** - Cloud database for users, games, and analysis
- **Redis Cache** - Fast data retrieval
- **Automatic migrations** - Alembic database versioning
- **Data persistence** - All analysis results saved

---

## 💻 System Requirements

### Required Software

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.11+ | Backend API |
| **Node.js** | 18+ | Frontend |
| **Redis** | 7+ | Caching & task queue |
| **Docker** | 20+ (optional) | Redis containerization |
| **Git** | Latest | Version control |

### Operating System Support

- ✅ **Windows** 10/11
- ✅ **macOS** 12+
- ✅ **Linux** (Ubuntu 20.04+, Debian, etc.)

### Hardware Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4 GB
- Storage: 2 GB free space

**Recommended:**
- CPU: 4+ cores
- RAM: 8 GB
- Storage: 5 GB free space

---

## 🏗 Deployment Architecture

### Hybrid Setup (Current Configuration)

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR PC / SERVER                        │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Frontend   │  │   Backend    │  │    Celery    │    │
│  │  (Next.js)   │  │  (FastAPI)   │  │    Worker    │    │
│  │  Port 3000   │  │  Port 8000   │  │   (Python)   │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                  │             │
│         └─────────────────┼──────────────────┘             │
│                           │                                │
│                  ┌────────▼────────┐                       │
│                  │  Redis (Docker) │                       │
│                  │   Port 6379     │                       │
│                  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Internet
                           │
                  ┌────────▼────────┐
                  │    Supabase     │
                  │  (PostgreSQL)   │
                  │   Cloud DB      │
                  └─────────────────┘
```

### Components

| Component | Deployment | Why |
|-----------|-----------|-----|
| **Redis** | Docker (recommended) or Local | Easy setup, isolated |
| **Backend** | Local (Python) | Needs local Stockfish, Supabase connection |
| **Celery Worker** | Local (Python) | Needs local Stockfish engine |
| **Frontend** | Local (Node.js) | Development mode |
| **PostgreSQL** | Supabase Cloud | Managed, scalable, free tier |

---

## 📦 Installation Guide

### Step 1: Clone Repository

```bash
git clone <your-repository-url>
cd chess-AI
```

### Step 2: Install Prerequisites

#### Windows

**Install Python 3.11+:**
```bash
# Download from python.org
# Or use winget:
winget install Python.Python.3.11
```

**Install Node.js 18+:**
```bash
# Download from nodejs.org
# Or use winget:
winget install OpenJS.NodeJS.LTS
```

**Install Docker Desktop (for Redis):**
```bash
# Download from docker.com
# Or use winget:
winget install Docker.DockerDesktop
```

**Install Redis (Alternative - without Docker):**
```bash
# Download from: https://github.com/microsoftarchive/redis/releases
# Or use Chocolatey:
choco install redis-64
```

#### macOS

```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install prerequisites
brew install python@3.11
brew install node@18
brew install redis  # Or use Docker
brew install --cask docker
```

#### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install Redis
sudo apt install redis-server

# Install Docker (optional)
sudo apt install docker.io docker-compose
```

### Step 3: Set Up Supabase (Cloud Database)

1. **Create Supabase Account:**
   - Go to [supabase.com](https://supabase.com)
   - Sign up for free account

2. **Create New Project:**
   - Click "New Project"
   - Choose organization
   - Set project name: `chess-insight-ai`
   - Set database password (save this!)
   - Choose region (closest to you)
   - Click "Create new project"

3. **Get Connection Details:**
   - Go to: Settings → Database
   - Find "Connection string" section
   - Copy the **URI** connection string
   - It looks like: `postgresql://postgres.PROJECT_REF:[PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres`

4. **Save Credentials:**
   - Keep your connection string safe
   - You'll need it for `.env` configuration

### Step 4: Install Stockfish Engine

#### Windows

```bash
# Download Stockfish 16 from:
# https://stockfishchess.org/download/

# Extract to: backend/stockfish/stockfish.exe
# Or any location and update .env
```

#### macOS

```bash
brew install stockfish

# Stockfish will be at: /opt/homebrew/bin/stockfish
```

#### Linux

```bash
sudo apt install stockfish

# Stockfish will be at: /usr/games/stockfish
```

### Step 5: Install Python Dependencies

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 6: Install Frontend Dependencies

```bash
cd frontend
npm install
```

### Step 7: Start Redis

**Option A: Using Docker (Recommended)**

```bash
# From project root
docker-compose up redis -d

# Verify Redis is running
docker ps
```

**Option B: Local Redis**

```bash
# Windows (if installed via installer)
# Redis runs as Windows service automatically

# macOS
brew services start redis

# Linux
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify Redis
redis-cli ping
# Should return: PONG
```

---

## ⚙️ Configuration

### Create `.env` File

```bash
# Copy example file
cp .env.example .env

# Edit .env with your settings
```

### Required Environment Variables

```bash
# ============================================================================
# Supabase Configuration
# ============================================================================
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# ============================================================================
# Database Configuration (PostgreSQL via Supabase)
# ============================================================================
# Get from: Supabase Dashboard → Settings → Database → Connection String (URI)
DATABASE_URL=postgresql://postgres.PROJECT_REF:[PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres

# ============================================================================
# Redis Configuration (for caching and Celery)
# ============================================================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://localhost:6379/0

# ============================================================================
# Celery Configuration
# ============================================================================
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# ============================================================================
# Stockfish Chess Engine
# ============================================================================
# Windows example:
STOCKFISH_PATH=E:\chess\chess-AI\backend\stockfish\stockfish.exe
# macOS example:
# STOCKFISH_PATH=/opt/homebrew/bin/stockfish
# Linux example:
# STOCKFISH_PATH=/usr/games/stockfish

STOCKFISH_DEPTH=15
STOCKFISH_TIME=1.0

# ============================================================================
# API Keys (Optional - for AI-enhanced analysis)
# ============================================================================
OPENAI_API_KEY=your_openai_key_here  # Optional
OPENROUTER_API_KEY=your_openrouter_key_here  # Optional

# ============================================================================
# Application Settings
# ============================================================================
PROJECT_NAME=Chess Insight AI
VERSION=1.0.0
ENVIRONMENT=development
LOG_LEVEL=INFO

# Chess.com API
CHESSCOM_API_BASE_URL=https://api.chess.com/pub
CHESSCOM_API_RATE_LIMIT=100

# CORS Origins
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=11520
```

### Get Supabase Keys

1. Go to: Supabase Dashboard → Settings → API
2. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_ANON_KEY`
   - **service_role** key → `SUPABASE_SERVICE_ROLE_KEY`

### Database Setup

```bash
cd backend

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Run database migrations
alembic upgrade head

# Verify tables created
python test_db_connection.py
```

**Expected output:**
```
✅ Connected to database: postgres
Tables found: 4
   - users
   - games
   - game_analyses
   - user_insights
```

---

## 🚀 Running the Application

### Quick Start (3 Terminals Required)

#### Terminal 1: Backend API

```bash
cd backend

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Start backend
python -m uvicorn app.__main__:app --reload

# Backend will be available at:
# http://localhost:8000
# API docs at: http://localhost:8000/docs
```

#### Terminal 2: Celery Worker

```bash
cd backend

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Start Celery worker
python start_celery_worker.py

# You should see:
# ======================================================================
# Starting Celery Worker for Chess AI
# ======================================================================
# celery@YOUR-PC ready.
```

#### Terminal 3: Frontend

```bash
cd frontend

# Start development server
npm run dev

# Frontend will be available at:
# http://localhost:3000
```

### Access the Application

1. **Open browser:** http://localhost:3000
2. **Create user:** Enter Chess.com username
3. **Fetch games:** Click "Fetch Games"
4. **Analyze games:** Click "Analyze" on any game
5. **View insights:** See performance metrics and recommendations

---

## 🧪 Testing the Setup

### Test Redis Connection

```bash
redis-cli ping
# Should return: PONG
```

### Test Database Connection

```bash
cd backend
python test_db_connection.py
```

### Test Redis Caching

```bash
cd backend
python test_redis_cache.py
```

**Expected output:**
```
✅ Cache HIT: chesscom:archives:magnuscarlsen:2024:01
Speed improvement: 118.6x faster
```

### Test Rate Limiting

```bash
cd backend
python test_rate_limiting.py
```

**Expected output:**
```
✅ Rate limit enforced correctly!
   - User ID: 999
   - Current count: 51/50
   - Retry after: 45 seconds
```

### Test Celery Worker

```bash
cd backend
python test_celery_demo.py
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Redis Connection Error

**Error:** `Redis connection failed`

**Solutions:**
```bash
# Check if Redis is running
docker ps  # If using Docker
redis-cli ping  # If local Redis

# Start Redis
docker-compose up redis -d  # Docker
brew services start redis  # macOS
sudo systemctl start redis-server  # Linux
```

#### 2. Database Connection Error

**Error:** `Could not translate host name`

**Solutions:**
- Verify `DATABASE_URL` in `.env` is correct
- Copy connection string from Supabase Dashboard
- Ensure password is correct (no placeholders)
- Check internet connection

#### 3. Stockfish Not Found

**Error:** `Stockfish engine not found`

**Solutions:**
```bash
# Verify Stockfish path in .env
# Windows example:
STOCKFISH_PATH=E:\chess\chess-AI\backend\stockfish\stockfish.exe

# Test Stockfish
stockfish  # Should open Stockfish console
```

#### 4. Celery Worker Not Starting

**Error:** `TypeError: Context.__init__() got an unexpected keyword argument 'app'`

**Solution:**
- This is already fixed in `start_celery_worker.py`
- Make sure you're using the latest version
- Run: `python start_celery_worker.py`

#### 5. Port Already in Use

**Error:** `Address already in use: 8000`

**Solutions:**
```bash
# Windows - Find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

#### 6. Frontend Build Errors

**Error:** `Module not found`

**Solutions:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

#### 7. Alembic Migration Errors

**Error:** `'%' must be followed by '%'`

**Solution:**
- This is already fixed in `alembic.ini`
- Lines 41, 109-110 have proper escaping
- Run: `alembic upgrade head`

---

## 📚 API Documentation

### Access Interactive API Docs

**Swagger UI:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc

### Key Endpoints

#### Users
- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/` - List users
- `GET /api/v1/users/{user_id}` - Get user details
- `GET /api/v1/users/by-username/{username}` - Get user by Chess.com username

#### Games
- `POST /api/v1/games/{user_id}/fetch` - Fetch games from Chess.com
- `GET /api/v1/games/{user_id}` - Get user's games
- `GET /api/v1/games/{user_id}/{game_id}` - Get specific game

#### Analysis
- `POST /api/v1/analysis/{user_id}/analyze/{game_id}` - Analyze single game
- `POST /api/v1/analysis/{user_id}/analyze` - Analyze multiple games
- `GET /api/v1/analysis/{user_id}/summary` - Get analysis summary
- `GET /api/v1/analysis/game/{game_id}` - Get game analysis results

#### Insights
- `GET /api/v1/insights/{user_id}/recommendations` - Get personalized recommendations
- `POST /api/v1/insights/{user_id}/generate` - Generate insights

---

## 🎯 Usage Guide

### 1. Create User

```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{"chesscom_username": "your_username"}'
```

### 2. Fetch Games

```bash
curl -X POST http://localhost:8000/api/v1/games/1/fetch \
  -H "Content-Type: application/json" \
  -d '{"days": 30}'
```

### 3. Analyze Game

```bash
curl -X POST http://localhost:8000/api/v1/analysis/1/analyze/1
```

### 4. View Analysis

```bash
curl http://localhost:8000/api/v1/analysis/game/1
```

---

## 🔐 Security Notes

### Production Deployment

**Before deploying to production:**

1. **Change SECRET_KEY:**
   ```bash
   # Generate secure key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Update CORS Origins:**
   ```bash
   BACKEND_CORS_ORIGINS=https://yourdomain.com
   ```

3. **Use Environment Variables:**
   - Never commit `.env` to Git
   - Use environment variables in production
   - Rotate API keys regularly

4. **Enable HTTPS:**
   - Use SSL certificates
   - Configure reverse proxy (Nginx/Caddy)

---

## 📊 Performance Optimization

### Redis Caching Benefits

- **Cache Hit Rate:** 95%+ for repeated requests
- **Speed Improvement:** 118x faster for cached data
- **API Call Reduction:** 50-67% fewer Chess.com API calls

### Rate Limiting

- **Per-user limit:** 50 requests per minute
- **Auto-reset:** 60-second TTL
- **Fair distribution:** Each user gets independent quota

---

## 🆘 Getting Help

### Resources

- **Documentation:** Check `/docs` folder
- **API Docs:** http://localhost:8000/docs
- **Test Scripts:** `/backend/test_*.py` files

### Common Commands

```bash
# Check Redis
redis-cli ping

# Check Database
python test_db_connection.py

# Check Celery
python test_celery_demo.py

# View logs
# Backend logs in terminal
# Celery logs in worker terminal
```

---

## 📝 Development Notes

### Project Structure

```
chess-AI/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   ├── core/              # Configuration
│   │   ├── models/            # Database models
│   │   ├── services/          # Business logic
│   │   │   ├── integration/   # Chess.com API
│   │   │   └── analysis/      # Game analysis
│   │   └── tasks/             # Celery tasks
│   ├── alembic/               # Database migrations
│   ├── stockfish/             # Stockfish engine
│   └── tests/                 # Test files
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Next.js pages
│   │   └── services/          # API clients
│   └── public/                # Static assets
└── docs/                      # Documentation
```

### Tech Stack

**Backend:**
- FastAPI 0.104.1
- SQLAlchemy 2.0.23
- Celery 5.3.4
- Redis 5.0.1
- Stockfish 16
- Python-chess 1.999

**Frontend:**
- Next.js 14.0.3
- React 18.2.0
- TypeScript 5.2.2
- Tailwind CSS 3.3.5
- Recharts 2.8.0

**Infrastructure:**
- Supabase (PostgreSQL)
- Redis 7
- Docker (optional)

---

## ✅ Checklist

Before running the application, ensure:

- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] Redis running (Docker or local)
- [ ] Supabase project created
- [ ] `.env` file configured
- [ ] Database migrations run
- [ ] Stockfish engine installed
- [ ] Python dependencies installed
- [ ] Frontend dependencies installed

---

## 🎉 You're Ready!

Your Chess Insight AI application should now be running successfully!

**Access points:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**Happy analyzing! ♟️**
