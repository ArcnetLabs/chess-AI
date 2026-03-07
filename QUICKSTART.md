# 🚀 Chess AI - Quick Start Guide

Get your Chess AI application running in 5 minutes!

---

## 🐳 Option 1: Docker (Recommended)

### Prerequisites
- Docker Desktop installed
- 4GB RAM available
- 10GB disk space

### Steps
```bash
# 1. Clone repository
git clone https://github.com/yourusername/chess-AI.git
cd chess-AI

# 2. Set up environment
cp .env.production.example .env.production

# 3. Generate secrets (Windows PowerShell)
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy output to SECRET_KEY in .env.production

python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy output to JWT_SECRET_KEY in .env.production

# 4. Start all services
docker-compose -f docker-compose.production.yml up -d

# 5. Wait for services to start (30-60 seconds)
docker-compose -f docker-compose.production.yml logs -f

# 6. Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/api/v1/docs
```

### Verify Installation
```bash
# Check health
curl http://localhost:8000/health

# Should return: {"status":"healthy"}
```

---

## 💻 Option 2: Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use SQLite)
- Redis 7+
- Stockfish chess engine

### Backend Setup
```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env with your values

# 5. Install Stockfish
# Windows: Download from stockfishchess.org
# Mac: brew install stockfish
# Linux: apt-get install stockfish

# 6. Run migrations
alembic upgrade head

# 7. Create indexes
python add_indexes.py

# 8. Start backend
python -m app

# Backend runs on http://localhost:8000
```

### Frontend Setup
```bash
# 1. Navigate to frontend (new terminal)
cd frontend

# 2. Install dependencies
npm install

# 3. Set up environment
cp .env.example .env.local
# Edit NEXT_PUBLIC_API_URL=http://localhost:8000

# 4. Start frontend
npm run dev

# Frontend runs on http://localhost:3000
```

### Celery Worker (Optional - for game analysis)
```bash
# New terminal, activate venv
cd backend
venv\Scripts\activate

# Start Redis (required)
# Windows: Download from redis.io
# Mac: brew services start redis
# Linux: sudo systemctl start redis

# Start Celery worker
celery -A app.celery_app worker --loglevel=info --pool=solo -Q analysis
```

---

## 🧪 Test Your Setup

### 1. Create a User
```bash
# Visit http://localhost:3000
# Enter Chess.com username: hikaru
# Click "Analyze with AI"
```

### 2. Verify Backend
```bash
# Check API docs
open http://localhost:8000/api/v1/docs

# Test health endpoint
curl http://localhost:8000/health
```

### 3. Test Game Analysis
```bash
# Should see Celery worker processing games
# Check logs: docker-compose logs -f celery
```

---

## 🛠️ Troubleshooting

### Issue: Docker containers won't start
```bash
# Check Docker is running
docker ps

# Check logs
docker-compose -f docker-compose.production.yml logs

# Restart services
docker-compose -f docker-compose.production.yml restart
```

### Issue: Backend can't connect to database
```bash
# Check DATABASE_URL in .env.production
# Should be: postgresql://chess_user:password@postgres:5432/chess_ai

# Test connection
docker-compose -f docker-compose.production.yml exec backend python -c "from app.core.database import engine; engine.connect()"
```

### Issue: Stockfish not found
```bash
# Docker: Already included
# Local: Install Stockfish
# Windows: Download from stockfishchess.org
# Mac: brew install stockfish
# Linux: apt-get install stockfish

# Verify installation
stockfish --version
```

### Issue: Frontend can't reach backend
```bash
# Check NEXT_PUBLIC_API_URL in .env.local
# Should be: http://localhost:8000

# Check CORS in backend .env
# BACKEND_CORS_ORIGINS should include http://localhost:3000
```

---

## 📚 Next Steps

1. **Read Documentation**
   - [Production Readiness](docs/PRODUCTION_READINESS.md)
   - [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md)
   - [Docker Guide](docs/deployment/DOCKER_GUIDE.md)
   - [Netlify Guide](docs/deployment/NETLIFY_DEPLOYMENT.md)

2. **Configure for Production**
   - Set up authentication
   - Add database migrations
   - Configure monitoring
   - Set up backups

3. **Deploy to Cloud**
   - Choose hosting platform:
     - **Full App:** Docker + Render/Railway
     - **Frontend Only:** Netlify + Separate Backend
     - **Enterprise:** AWS/GCP/Azure
   - Follow deployment guide
   - Configure domain and SSL

---

## 🎯 Default Credentials

**Note:** This is a username-only system (no passwords yet)

- Test with any valid Chess.com username
- Example: `hikaru`, `magnuscarlsen`, `gothamchess`

---

## 📊 System Requirements

### Minimum
- 2 CPU cores
- 4GB RAM
- 10GB disk space
- Internet connection

### Recommended
- 4 CPU cores
- 8GB RAM
- 20GB SSD
- Stable internet

---

## 🆘 Getting Help

- **Documentation:** [docs/README.md](docs/README.md)
- **Issues:** [GitHub Issues](https://github.com/yourusername/chess-AI/issues)
- **Email:** support@chess-ai.com

---

## ✅ Quick Checklist

- [ ] Docker installed (or Python + Node.js)
- [ ] Repository cloned
- [ ] Environment variables configured
- [ ] Secrets generated
- [ ] Services started
- [ ] Health check passed
- [ ] Test user created
- [ ] Game analysis working

---

**Ready to deploy?** See [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md)

**Need help?** Check [Troubleshooting](docs/deployment/DOCKER_GUIDE.md#troubleshooting)
