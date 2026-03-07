# 🐳 Docker Deployment Guide

## Quick Start

### 1. Prerequisites
```bash
# Install Docker
# Windows: Download Docker Desktop from docker.com
# Mac: Download Docker Desktop from docker.com
# Linux: 
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose (usually included with Docker Desktop)
docker-compose --version
```

### 2. Clone and Setup
```bash
# Clone repository
git clone https://github.com/yourusername/chess-AI.git
cd chess-AI

# Copy environment file
cp .env.production.example .env.production

# Generate secrets
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env.production
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env.production
```

### 3. Configure Environment
Edit `.env.production` and update:
```env
# Update these values
POSTGRES_PASSWORD=your_secure_password_here
REDIS_PASSWORD=your_redis_password_here
BACKEND_CORS_ORIGINS=https://your-domain.com
NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

### 4. Build and Run
```bash
# Build images
docker-compose -f docker-compose.production.yml build

# Start all services
docker-compose -f docker-compose.production.yml up -d

# Check status
docker-compose -f docker-compose.production.yml ps

# View logs
docker-compose -f docker-compose.production.yml logs -f
```

### 5. Verify Deployment
```bash
# Check backend health
curl http://localhost:8000/health

# Check frontend
curl http://localhost:3000

# Check API docs
open http://localhost:8000/api/v1/docs
```

---

## 🏗️ Architecture

### Services Overview
```
┌─────────────────────────────────────────────────┐
│                   Frontend                      │
│              (Next.js - Port 3000)              │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│                   Backend API                   │
│            (FastAPI - Port 8000)                │
└────┬──────────────────────────────────┬─────────┘
     │                                   │
     ▼                                   ▼
┌─────────────┐                    ┌──────────────┐
│  PostgreSQL │                    │    Redis     │
│  (Port 5432)│                    │  (Port 6379) │
└─────────────┘                    └──────┬───────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │Celery Worker │
                                   │  (Stockfish) │
                                   └──────────────┘
```

### Container Details

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **frontend** | Node 18 Alpine | 3000 | React/Next.js UI |
| **backend** | Python 3.11 Slim | 8000 | FastAPI REST API |
| **celery** | Python 3.11 Slim | - | Background analysis |
| **postgres** | PostgreSQL 15 | 5432 | Database |
| **redis** | Redis 7 Alpine | 6379 | Cache & Queue |

---

## 📋 Docker Commands Reference

### Basic Operations
```bash
# Start all services
docker-compose -f docker-compose.production.yml up -d

# Stop all services
docker-compose -f docker-compose.production.yml down

# Restart a specific service
docker-compose -f docker-compose.production.yml restart backend

# View logs
docker-compose -f docker-compose.production.yml logs -f [service-name]

# Check status
docker-compose -f docker-compose.production.yml ps
```

### Database Operations
```bash
# Run migrations
docker-compose -f docker-compose.production.yml exec backend alembic upgrade head

# Create indexes
docker-compose -f docker-compose.production.yml exec backend python add_indexes.py

# Access PostgreSQL shell
docker-compose -f docker-compose.production.yml exec postgres psql -U chess_user -d chess_ai

# Backup database
docker-compose -f docker-compose.production.yml exec postgres pg_dump -U chess_user chess_ai > backup.sql

# Restore database
docker-compose -f docker-compose.production.yml exec -T postgres psql -U chess_user chess_ai < backup.sql
```

### Debugging
```bash
# Execute command in container
docker-compose -f docker-compose.production.yml exec backend bash

# View container logs
docker logs chess-ai-backend --tail 100 -f

# Inspect container
docker inspect chess-ai-backend

# Check resource usage
docker stats
```

### Cleanup
```bash
# Stop and remove containers
docker-compose -f docker-compose.production.yml down

# Remove volumes (WARNING: deletes data)
docker-compose -f docker-compose.production.yml down -v

# Remove images
docker-compose -f docker-compose.production.yml down --rmi all

# Clean up unused resources
docker system prune -a
```

---

## 🔧 Configuration

### Environment Variables

#### Backend Service
```yaml
environment:
  - DATABASE_URL=postgresql://user:pass@postgres:5432/db
  - REDIS_URL=redis://:pass@redis:6379/0
  - SECRET_KEY=${SECRET_KEY}
  - STOCKFISH_PATH=/usr/games/stockfish
  - ENVIRONMENT=production
```

#### Frontend Service
```yaml
environment:
  - NEXT_PUBLIC_API_URL=http://backend:8000
```

### Volume Mounts
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data  # Database persistence
  - redis_data:/data                        # Redis persistence
  - ./backend/uploads:/app/uploads          # File uploads
```

### Health Checks
All services include health checks:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## 🚀 Production Deployment

### Option 1: Single Server (VPS)

#### 1. Prepare Server
```bash
# SSH into server
ssh user@your-server.com

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. Clone and Configure
```bash
# Clone repository
git clone https://github.com/yourusername/chess-AI.git
cd chess-AI

# Set up environment
cp .env.production.example .env.production
nano .env.production  # Edit with your values
```

#### 3. Deploy
```bash
# Build and start
docker-compose -f docker-compose.production.yml up -d

# Check logs
docker-compose -f docker-compose.production.yml logs -f
```

#### 4. Set Up Nginx Reverse Proxy
```nginx
# /etc/nginx/sites-available/chess-ai
server {
    listen 80;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/chess-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Set up SSL with Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d api.your-domain.com
```

---

### Option 2: Docker Swarm (Multi-Server)

#### 1. Initialize Swarm
```bash
# On manager node
docker swarm init --advertise-addr <MANAGER-IP>

# On worker nodes
docker swarm join --token <TOKEN> <MANAGER-IP>:2377
```

#### 2. Deploy Stack
```bash
# Deploy services
docker stack deploy -c docker-compose.production.yml chess-ai

# Check services
docker service ls

# Scale services
docker service scale chess-ai_backend=3
```

---

### Option 3: Kubernetes (Advanced)

See `docs/deployment/kubernetes/` for K8s manifests.

---

## 📊 Monitoring

### View Logs
```bash
# All services
docker-compose -f docker-compose.production.yml logs -f

# Specific service
docker-compose -f docker-compose.production.yml logs -f backend

# Last 100 lines
docker-compose -f docker-compose.production.yml logs --tail=100 backend
```

### Resource Usage
```bash
# Real-time stats
docker stats

# Container inspection
docker inspect chess-ai-backend
```

### Health Checks
```bash
# Backend
curl http://localhost:8000/health

# Database
docker-compose -f docker-compose.production.yml exec postgres pg_isready

# Redis
docker-compose -f docker-compose.production.yml exec redis redis-cli ping
```

---

## 🔒 Security Best Practices

### 1. Use Secrets Management
```bash
# Don't use .env files in production
# Use Docker secrets instead
echo "my_secret_password" | docker secret create db_password -

# Reference in docker-compose.yml
secrets:
  - db_password
```

### 2. Run as Non-Root User
```dockerfile
# In Dockerfile
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

### 3. Limit Resources
```yaml
# In docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 4. Network Isolation
```yaml
# Create separate networks
networks:
  frontend:
  backend:
  database:
```

---

## 🐛 Troubleshooting

### Issue: Container won't start
```bash
# Check logs
docker-compose -f docker-compose.production.yml logs backend

# Check if port is in use
netstat -tulpn | grep 8000

# Restart service
docker-compose -f docker-compose.production.yml restart backend
```

### Issue: Database connection failed
```bash
# Check if PostgreSQL is running
docker-compose -f docker-compose.production.yml ps postgres

# Test connection
docker-compose -f docker-compose.production.yml exec backend python -c "from app.core.database import engine; engine.connect()"

# Check DATABASE_URL
docker-compose -f docker-compose.production.yml exec backend env | grep DATABASE_URL
```

### Issue: Stockfish not found
```bash
# Verify Stockfish installation
docker-compose -f docker-compose.production.yml exec backend which stockfish
docker-compose -f docker-compose.production.yml exec backend stockfish --version

# Reinstall if needed
docker-compose -f docker-compose.production.yml exec backend apt-get update && apt-get install -y stockfish
```

### Issue: Out of memory
```bash
# Check memory usage
docker stats

# Increase memory limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
```

---

## 🔄 Updates and Maintenance

### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild images
docker-compose -f docker-compose.production.yml build

# Restart services
docker-compose -f docker-compose.production.yml up -d

# Run migrations
docker-compose -f docker-compose.production.yml exec backend alembic upgrade head
```

### Backup Strategy
```bash
# Automated backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose -f docker-compose.production.yml exec postgres pg_dump -U chess_user chess_ai > backup_$DATE.sql
gzip backup_$DATE.sql
aws s3 cp backup_$DATE.sql.gz s3://your-backup-bucket/
```

---

## 📞 Support

For Docker-related issues:
1. Check logs: `docker-compose logs`
2. Review this guide
3. Check Docker documentation
4. Open GitHub issue

---

## 🎯 Next Steps

1. ✅ Set up Docker on your server
2. ✅ Configure environment variables
3. ✅ Deploy with docker-compose
4. ⏳ Set up monitoring
5. ⏳ Configure backups
6. ⏳ Set up CI/CD
