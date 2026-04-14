# Phase 1 Deployment Guide

## Prerequisites

Before deploying Phase 1, ensure:
- ✅ Docker Desktop is running
- ✅ PostgreSQL/SQLite database is accessible
- ✅ All dependencies installed: `pip install -r requirements.txt`
- ✅ Redis is running (optional, will fallback to development mode)

---

## Deployment Steps

### Step 1: Install Dependencies (if needed)

```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Run Database Migration

```bash
cd backend
python -m alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade 0002 -> 0003, add_enhanced_recommendation_fields
```

**Verify Migration:**
```sql
-- Check new columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_insights' 
AND column_name IN ('recommendation_scores', 'focus_areas_detailed', 'pattern_matches');
```

### Step 3: Start/Restart Services

**Using Docker Compose:**
```bash
cd ..
docker-compose up -d
# or restart if already running
docker-compose restart backend
```

**Using Uvicorn (development):**
```bash
cd backend
uvicorn app.__main__:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Verify Backend is Running

```bash
curl http://localhost:8000/health
# or
curl http://localhost:8000/docs
```

### Step 5: Test Enhanced Recommendations

#### 5a. Generate Insights for a User

```bash
# Replace {user_id} with actual user ID
curl -X POST http://localhost:8000/api/insights/1/generate \
  -H "Content-Type: application/json" \
  -d '{"period_days": 7, "analysis_type": "weekly"}'
```

**Expected Response:**
```json
{
  "message": "Insights generation queued for 7 day period",
  "period_start": "2026-03-14T...",
  "period_end": "2026-03-21T..."
}
```

#### 5b. Check Coaching Plan (New Endpoint)

```bash
curl http://localhost:8000/api/insights/1/coaching-plan
```

**Expected Response:**
```json
{
  "recommendations": [
    {
      "category": "endgame",
      "priority": "high",
      "priority_score": 78.5,
      "title": "Endgame Technique Needs Improvement",
      "description": "Your endgame ACPL is 45.2...",
      "actionable_steps": [
        "Study fundamental endgames: King and Pawn, Rook endgames",
        "Practice endgame positions on Lichess Studies",
        ...
      ],
      "resources": [...],
      "pattern_match": {
        "pattern_name": "high_endgame_acpl",
        "severity": 0.75,
        "frequency": 8,
        "evidence": {...}
      }
    }
  ],
  "priority_scores": [78.5, 72.3, 65.1],
  "pattern_matches": [...],
  "performance_summary": {...},
  "period": {...}
}
```

#### 5c. Check Latest Insight (Existing Endpoint)

```bash
curl http://localhost:8000/api/insights/1/latest
```

**Verify:**
- ✅ `recommendations` field contains enhanced recommendations
- ✅ `recommendation_scores` field exists (new)
- ✅ `pattern_matches` field exists (new)

### Step 6: Monitor Logs

```bash
# Docker
docker-compose logs -f backend | grep -i "recommendation"

# Direct
tail -f logs/backend.log | grep -i "recommendation"
```

**Look for:**
```
INFO: Generated 5 enhanced recommendations for user 1
INFO: Enhanced recommendation engine failed, using basic recommendations: ...
```

---

## Verification Checklist

### Database
- [ ] Migration ran successfully
- [ ] New columns exist in `user_insights` table
- [ ] Index created on `user_id, period_end`

### API Endpoints
- [ ] `POST /api/insights/{user_id}/generate` works
- [ ] `GET /api/insights/{user_id}/coaching-plan` returns data
- [ ] `GET /api/insights/{user_id}/latest` includes new fields

### Functionality
- [ ] Enhanced recommendations generated (check logs)
- [ ] Fallback to basic recommendations works (if engine fails)
- [ ] Priority scores calculated correctly
- [ ] Pattern matches included in response

### Backward Compatibility
- [ ] Existing insights endpoints work unchanged
- [ ] Old insights data still accessible
- [ ] No errors in existing functionality

---

## Troubleshooting

### Issue: Migration Fails with "Multiple heads"

**Solution:**
```bash
# Merge the heads first
python -m alembic merge heads -m "merge heads"
python -m alembic upgrade head
```

### Issue: "No module named 'celery'"

**Solution:**
```bash
pip install celery==5.3.4
```

### Issue: Enhanced recommendations not generating

**Check:**
1. Logs for error messages
2. User has analyzed games (minimum 3 games recommended)
3. Recommendation engine import successful

**Debug:**
```python
# In Python shell
from app.services.coaching.recommendation_engine import RecommendationEngine
engine = RecommendationEngine()
# Should not raise errors
```

### Issue: "Enhanced recommendation engine failed"

**This is expected behavior** - the system falls back to basic recommendations. Check logs for the specific error.

### Issue: Database columns not created

**Verify migration ran:**
```bash
python -m alembic current
# Should show: 0003 (head)
```

**Manually check database:**
```sql
\d user_insights  -- PostgreSQL
.schema user_insights  -- SQLite
```

---

## Rollback Procedure

If you need to rollback the changes:

### 1. Rollback Database
```bash
cd backend
python -m alembic downgrade -1
```

### 2. Rollback Code
```bash
git revert <commit-hash>
```

### 3. Restart Services
```bash
docker-compose restart backend
```

### 4. Verify Rollback
```bash
curl http://localhost:8000/api/insights/1/latest
# Should work with basic recommendations only
```

---

## Performance Monitoring

### Database Query Performance
```sql
-- Check index usage
EXPLAIN ANALYZE 
SELECT * FROM user_insights 
WHERE user_id = 1 
ORDER BY period_end DESC 
LIMIT 1;
```

### API Response Times
```bash
# Time the coaching plan endpoint
time curl http://localhost:8000/api/insights/1/coaching-plan
```

**Expected:** < 500ms for cached data

### Memory Usage
```bash
docker stats backend
```

---

## Success Indicators

✅ **Deployment Successful When:**
- Migration completes without errors
- New API endpoint returns data
- Enhanced recommendations appear in logs
- No errors in existing functionality
- Response times acceptable (<1s)

---

## Next Steps After Deployment

1. **Monitor for 24 hours**
   - Check error logs
   - Verify recommendation quality
   - Monitor performance metrics

2. **Collect User Feedback**
   - Are recommendations helpful?
   - Are actionable steps clear?
   - Is priority scoring accurate?

3. **Iterate on Pattern Rules**
   - Adjust thresholds based on data
   - Add new pattern rules if needed
   - Refine priority scoring weights

4. **Begin Phase 2 Planning**
   - Move Recommendation System
   - Real-time position analysis
   - Interactive chessboard

---

## Support

**Documentation:**
- Implementation: `backend/PHASE1_IMPLEMENTATION_COMPLETE.md`
- API Docs: `http://localhost:8000/docs`
- Coaching Services: `backend/app/services/coaching/README.md`

**Testing:**
- Test Suite: `backend/tests/test_recommendation_engine.py`
- Run Tests: `pytest tests/test_recommendation_engine.py -v`

---

**Deployment Guide Version:** 1.0  
**Last Updated:** March 21, 2026  
**Phase:** 1 - Enhanced Recommendations
