# 🔧 UX Fixes & Improvements Needed

## **Issues Identified by User** (Nov 2, 2025)

### **1. Game Count Confusion** ❌
**Problem**: User selected 25 games but sees 50 total games
**Root Cause**: Backend accumulates games instead of replacing
**Fix Needed**: 
- Add "Replace existing games" option to fetch endpoint
- OR: Clear games before each fetch
- Show clear messaging: "Fetched 25 new games (Total: 50)"

**Priority**: HIGH
**Status**: TODO

---

### **2. Pre-Analyzed Games** ❌
**Problem**: Fresh user sees "8 games analyzed" before running any analysis
**Root Cause**: Test data from Phase 2 testing still in Supabase
**Fix Needed**:
- Clear test data from Supabase
- Reset user stats (total_games, analyzed_games, ai_analyses_used)
- Ensure fresh user experience

**Priority**: CRITICAL
**Status**: IN PROGRESS (SQL script created)

---

### **3. Misleading "Recent Games" Label** ❌
**Problem**: "Recent Games" implies chronological, but it's "Fetched Games"
**Fix Needed**:
- Change label to "Fetched Games" or "Your Games (Last 25)"
- Add subtitle: "Games fetched from Chess.com"

**Priority**: MEDIUM
**Status**: TODO

---

### **4. No Dashboard Filters (Bad UX)** ❌
**Problem**: User must go back to landing page to re-fetch with different filters
**Fix Needed**:
- Add filter panel to dashboard (same as landing page)
- Add "Fetch More Games" button
- Add "Clear & Start Over" option
- Show current filter settings

**Priority**: HIGH
**Status**: TODO (This is Phase 5)

---

### **5. Analysis Not Saved/Retrievable** ❌
**Problem**: No way to view past analyses or compare over time
**Fix Needed**:
- Create `user_analysis_snapshots` table
- Save analysis results with timestamps
- Add "Analysis History" page
- Add "Compare Analyses" feature
- Add "Export Report" button

**Priority**: MEDIUM
**Status**: TODO (Post-Phase 5)

---

### **6. Analysis Workflow Unclear** ❌
**Problem**: 
- Games show "analyzed" before user clicks analyze
- No clear "Analyze Now" button
- No progress indicator during analysis

**Fix Needed**:
- Clear "Analyze Games" CTA on dashboard
- Show analysis progress modal
- Update game cards in real-time as analysis completes
- Show tier status (X AI analyses remaining)

**Priority**: HIGH
**Status**: PARTIAL (Modal exists, needs integration)

---

## **Implementation Plan**

### **Phase 3.5: Critical Fixes** (Do Now)
1. ✅ Clear Supabase test data
2. ✅ Change "Recent Games" → "Fetched Games"
3. ✅ Add clear messaging about game counts
4. ✅ Fix analysis workflow clarity

### **Phase 5: Dashboard Filters** (Next)
1. ✅ Add filter panel to dashboard
2. ✅ Add "Fetch More" functionality
3. ✅ Show tier status banner
4. ✅ Add "Clear & Restart" option

### **Phase 6: Analysis History** (Later)
1. ✅ Create analysis snapshots table
2. ✅ Save analysis results
3. ✅ Add history page
4. ✅ Add comparison feature

---

## **User Expectations (Correct Flow)**

### **Landing Page**
1. User enters username
2. User selects filters (25 games, rapid+blitz, rated)
3. User clicks "Get Started"
4. System fetches exactly 25 games
5. All games show "Not Analyzed"
6. Redirect to dashboard

### **Dashboard (Fresh State)**
- Shows "25 Fetched Games"
- All games: "Not Analyzed" tag
- No insights/recommendations (empty state)
- Clear "Analyze Games" button
- Tier status: "5 AI analyses remaining"

### **After Analysis**
- Selected games: "Analyzed" tag
- Insights panel: Populated with data
- Recommendations: Showing coaching tips
- Tier status: "4 AI analyses remaining"
- Can re-analyze or fetch more games

---

## **SQL Script to Reset User**

Run this in Supabase SQL Editor:

```sql
-- Reset user 1 for fresh testing
UPDATE users 
SET 
  total_games = 0,
  analyzed_games = 0,
  ai_analyses_used = 0
WHERE id = 1;

-- Delete all games and analyses
DELETE FROM game_analyses WHERE game_id IN (SELECT id FROM games WHERE user_id = 1);
DELETE FROM games WHERE user_id = 1;
```

---

## **Next Steps**

1. **User**: Run SQL script in Supabase to clear test data
2. **Dev**: Fix "Recent Games" label
3. **Dev**: Add dashboard filters (Phase 5)
4. **Dev**: Improve analysis workflow
5. **Test**: Full end-to-end flow with fresh data
