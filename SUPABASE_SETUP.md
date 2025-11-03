# 🚀 Running Backend with Supabase

## **The Issue**
Docker containers can't reach external Supabase database due to network isolation.

## **The Solution**
Run backend **locally** (not in Docker) to connect to Supabase.

---

## **Setup Steps**

### **1. Start Redis (in Docker)**
```bash
cd C:\Users\HP\chess-insight-ai
docker-compose up -d redis
```

### **2. Verify .env Configuration**
Check that `C:\Users\HP\chess-insight-ai\.env` has:
```env
DATABASE_URL=postgresql://postgres:2Klbylr8qz48O7ci@db.kkgdxjypcvvrnqtocazc.supabase.co:5432/postgres?sslmode=require
REDIS_HOST=localhost
REDIS_PORT=6379
```

### **3. Install Python Dependencies** (if not already done)
```bash
cd C:\Users\HP\chess-insight-ai\backend
pip install -r requirements.txt
```

### **4. Start Backend Locally**
```bash
cd C:\Users\HP\chess-insight-ai\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### **5. Verify Backend is Running**
Open browser: http://localhost:8000/docs

You should see the FastAPI Swagger documentation.

### **6. Test Supabase Connection**
```bash
curl http://localhost:8000/api/v1/users/
```

Expected: `[]` (empty array) since Supabase is fresh

---

## **Start Frontend**
```bash
cd C:\Users\HP\chess-insight-ai\frontend
npm run dev
```

Frontend will run on: http://localhost:3000

---

## **Full Flow Test**

1. Go to http://localhost:3000
2. Enter username: `gh_wilder`
3. Select filters: 25 games, rapid+blitz, rated
4. Click "Get Started"
5. Games will be fetched to Supabase
6. Check Supabase dashboard to see data

---

## **Troubleshooting**

### **Backend won't start**
- Check if port 8000 is already in use: `netstat -ano | findstr :8000`
- Kill process if needed: `taskkill /PID <PID> /F`
- Check Python version: `python --version` (should be 3.10+)

### **Can't connect to Supabase**
- Verify password in `.env` is correct
- Test connection manually:
  ```bash
  psql "postgresql://postgres:2Klbylr8qz48O7ci@db.kkgdxjypcvvrnqtocazc.supabase.co:5432/postgres?sslmode=require"
  ```

### **Redis connection error**
- Verify Redis is running: `docker ps`
- Should see `chess-insight-redis` container

---

## **Current Status**

✅ Docker-compose updated (local PostgreSQL disabled)
✅ Redis running in Docker
✅ `.env` configured for Supabase
⏳ Backend needs to start locally
⏳ Frontend running on port 3000

---

## **Next: Test Full Flow**

Once backend starts successfully:
1. Test game fetching with filters
2. Verify data in Supabase
3. Test analysis workflow
4. Implement Phase 5 (dashboard filters)
