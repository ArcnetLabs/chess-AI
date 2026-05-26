# 🚀 Deployment Guide - Chess AI Application

## Table of Contents
1. [Hosting Options](#hosting-options)
2. [Docker Deployment](#docker-deployment)
3. [Cloud Platform Guides](#cloud-platform-guides)
4. [Environment Configuration](#environment-configuration)
5. [Post-Deployment Checklist](#post-deployment-checklist)

---

## 🌐 Hosting Options

### Option 1: Render.com (Recommended for MVP) ⭐
**Pros:**
- ✅ Easy deployment from GitHub
- ✅ Free tier available
- ✅ Automatic HTTPS
- ✅ PostgreSQL included
- ✅ Zero DevOps knowledge required

**Cons:**
- ❌ Free tier sleeps after inactivity
- ❌ Limited customization
- ❌ Can be expensive at scale

**Cost:** $7-25/month (Starter), Free tier available

**Best For:** MVPs, demos, small projects

---

### Option 2: Railway.app
**Pros:**
- ✅ Simple deployment
- ✅ Great developer experience
- ✅ Built-in PostgreSQL & Redis
- ✅ Automatic scaling

**Cons:**
- ❌ More expensive than Render
- ❌ Credit-based pricing

**Cost:** $5-20/month (usage-based)

**Best For:** Startups, growing projects

---

### Option 3: AWS (Elastic Beanstalk / ECS)
**Pros:**
- ✅ Highly scalable
- ✅ Full control
- ✅ Enterprise-grade
- ✅ Many services available

**Cons:**
- ❌ Complex setup
- ❌ Requires DevOps knowledge
- ❌ Can be expensive

**Cost:** $50-500+/month

**Best For:** Production apps, enterprises

---

### Option 4: DigitalOcean App Platform
**Pros:**
- ✅ Simple deployment
- ✅ Predictable pricing
- ✅ Good documentation
- ✅ Managed databases

**Cons:**
- ❌ Less features than AWS
- ❌ Limited regions

**Cost:** $12-50/month

**Best For:** Mid-sized projects

---

### Option 5: Vercel (Frontend) + Render (Backend)
**Pros:**
- ✅ Best frontend performance
- ✅ Automatic deployments
- ✅ Free tier for frontend
- ✅ Great DX

**Cons:**
- ❌ Split deployment
- ❌ Need to manage CORS

**Cost:** $0-20/month

**Best For:** Optimized performance

---

### Option 6: Netlify (Frontend Only) + Separate Backend
**Pros:**
- ✅ Excellent static site hosting
- ✅ Global CDN included
- ✅ Automatic HTTPS
- ✅ Great developer experience
- ✅ Free tier available

**Cons:**
- ❌ Frontend only (backend separate)
- ❌ No server-side rendering
- ❌ Need separate backend hosting

**Cost:** $0-20/month (frontend only)

**Best For:** Static frontend with separate backend

---

### Option 7: Vercel (Frontend) + Render (Backend)
**Pros:**
- ✅ Best frontend performance
- ✅ Automatic deployments
- ✅ Free tier for frontend
- ✅ Great DX

**Cons:**
- ❌ Split deployment
- ❌ Need to manage CORS

**Cost:** $0-20/month

**Best For:** Optimized performance

---

### Option 8: Self-Hosted (VPS)
**Pros:**
- ✅ Full control
- ✅ Cheapest at scale
- ✅ No vendor lock-in

**Cons:**
- ❌ Requires DevOps expertise
- ❌ Manual scaling
- ❌ Security responsibility

**Cost:** $5-50/month (VPS)

**Best For:** Advanced users, cost optimization

---

## 🐳 Docker Deployment

### Quick Start
```bash
# Clone repository
git clone https://github.com/yourusername/chess-AI.git
cd chess-AI

# Set up environment variables
cp .env.example .env
# Edit .env with your values

# Build and run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Access Application
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/api/v1/docs

---

## 📦 Render.com Deployment (Step-by-Step)

### Prerequisites
- GitHub account
- Render.com account (free)
- Chess.com account for testing

### Step 1: Prepare Repository
```bash
# Ensure render.yaml exists (already in repo)
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### Step 2: Connect to Render
1. Go to [render.com](https://render.com)
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Select `chess-AI` repository
5. Render will detect `render.yaml`

### Step 3: Configure Environment Variables
In Render dashboard, set these for **chess-insight-backend** and **chess-insight-celery**:

```env
# Database — Supabase PostgreSQL (NOT Render Postgres)
# Use transaction pooler URI from Supabase dashboard (see infrastructure-stabilization-report.md)
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-1-[region].pooler.supabase.com:6543/postgres?sslmode=require

# Supabase Auth (backend JWT verification)
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=

# Redis — wired automatically from render.yaml chess-insight-redis service
REDIS_HOST=<from blueprint>
REDIS_PORT=<from blueprint>
REDIS_DB=0

# Security
SECRET_KEY=<generate-with-openssl-rand-hex-32>

# Stockfish
STOCKFISH_PATH=/usr/games/stockfish
STOCKFISH_DEPTH=15

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
BACKEND_CORS_ORIGINS=https://your-frontend-domain.com
```

> **Important:** Schema changes run via `alembic upgrade head` in the Render build step — not `create_all` at startup. The app fails fast if Postgres or (in production) Redis is unreachable.

See [`infrastructure-stabilization-report.md`](./infrastructure-stabilization-report.md) for the full P0 checklist and verification commands.

### Step 4: Configure Frontend Environment
Set for **frontend service**:

```env
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

### Step 5: Deploy
1. Click "Apply" in Render dashboard
2. Wait for build (5-10 minutes)
3. Services will auto-deploy

### Step 6: Install Stockfish on Render
Add to `render.yaml` (already included):
```yaml
buildCommand: |
  apt-get update
  apt-get install -y stockfish
  pip install -r requirements.txt
```

---

## 🚀 Railway.app Deployment

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### Step 2: Initialize Project
```bash
cd chess-AI
railway init
```

### Step 3: Add Services
```bash
# Add PostgreSQL
railway add --database postgres

# Add Redis
railway add --database redis

# Deploy backend
cd backend
railway up

# Deploy frontend
cd ../frontend
railway up
```

### Step 4: Configure Environment
```bash
railway variables set SECRET_KEY=<your-secret>
railway variables set STOCKFISH_PATH=/usr/games/stockfish
```

---

## ☁️ AWS Deployment (Docker + ECS)

### Prerequisites
- AWS account
- AWS CLI installed
- Docker installed

### Step 1: Create ECR Repositories
```bash
# Backend
aws ecr create-repository --repository-name chess-ai-backend

# Frontend
aws ecr create-repository --repository-name chess-ai-frontend
```

### Step 2: Build and Push Images
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push backend
cd backend
docker build -t chess-ai-backend .
docker tag chess-ai-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/chess-ai-backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/chess-ai-backend:latest

# Build and push frontend
cd ../frontend
docker build -t chess-ai-frontend .
docker tag chess-ai-frontend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/chess-ai-frontend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/chess-ai-frontend:latest
```

### Step 3: Create ECS Cluster
```bash
aws ecs create-cluster --cluster-name chess-ai-cluster
```

### Step 4: Create Task Definitions
See `docs/deployment/aws-task-definition.json`

### Step 5: Create Services
```bash
aws ecs create-service \
  --cluster chess-ai-cluster \
  --service-name chess-ai-backend \
  --task-definition chess-ai-backend \
  --desired-count 1 \
  --launch-type FARGATE
```

---

## 🔐 Environment Configuration

### Required Environment Variables

#### Backend (.env)
```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://host:6379/0

# Security
SECRET_KEY=<64-char-random-string>
JWT_SECRET_KEY=<64-char-random-string>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Stockfish
STOCKFISH_PATH=/usr/games/stockfish
STOCKFISH_DEPTH=15
STOCKFISH_TIME=1.0
STOCKFISH_THREADS=2
STOCKFISH_HASH=256

# OpenAI (optional)
OPENAI_API_KEY=sk-...

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO

# CORS
BACKEND_CORS_ORIGINS=https://your-frontend.com
```

#### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=https://your-backend.com
```

### Generate Secrets
```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## ✅ Post-Deployment Checklist

### 1. Health Checks
```bash
# Backend health
curl https://your-backend.com/health

# Frontend
curl https://your-frontend.com
```

### 2. Database Migrations
```bash
# Run migrations
docker exec -it backend alembic upgrade head

# Or via Railway
railway run alembic upgrade head
```

### 3. Create Indexes
```bash
# Run index creation script
docker exec -it backend python add_indexes.py
```

### 4. Test Core Functionality
- [ ] Create user
- [ ] Fetch games from Chess.com
- [ ] Analyze game with Stockfish
- [ ] View analysis results

### 5. Monitor Logs
```bash
# Docker
docker-compose logs -f

# Render
# View in dashboard

# Railway
railway logs
```

### 6. Set Up Monitoring
- [ ] Configure Sentry for error tracking
- [ ] Set up uptime monitoring (UptimeRobot)
- [ ] Configure log aggregation

### 7. Security
- [ ] Verify HTTPS is enabled
- [ ] Check CORS configuration
- [ ] Test rate limiting
- [ ] Review exposed endpoints

---

## 🔧 Troubleshooting

### Issue: Stockfish not found
```bash
# Install Stockfish
apt-get update && apt-get install -y stockfish

# Or download binary
wget https://stockfishchess.org/files/stockfish_15_linux_x64.zip
unzip stockfish_15_linux_x64.zip
chmod +x stockfish
mv stockfish /usr/local/bin/
```

### Issue: Database connection failed
```bash
# Check DATABASE_URL format
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL
```

### Issue: Redis connection failed
```bash
# Check REDIS_URL
echo $REDIS_URL

# Test connection
redis-cli -u $REDIS_URL ping
```

### Issue: Celery worker not starting
```bash
# Check logs
docker logs backend-celery

# Restart worker
docker-compose restart celery
```

---

## 📊 Monitoring & Maintenance

### Daily
- Check error rates in Sentry
- Monitor API response times
- Review Celery queue depth

### Weekly
- Review logs for anomalies
- Check database size
- Update dependencies

### Monthly
- Security updates
- Performance optimization
- Cost review

---

## 🎯 Next Steps

1. **Implement Authentication** (Critical)
2. **Add Tests** (Critical)
3. **Set Up CI/CD**
4. **Configure Monitoring**
5. **Optimize Performance**

---

## 📞 Support

For deployment issues:
- Check logs first
- Review this guide
- Open GitHub issue
- Contact: your-email@example.com
