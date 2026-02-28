# Individual Game Analysis Implementation

## Changes Made

### Backend Changes

#### 1. New API Endpoint (`backend/app/api/analysis.py`)
- Added `POST /api/v1/analysis/{user_id}/analyze/{game_id}` endpoint
- Allows analyzing individual games instead of batch analysis
- Returns status: `queued`, `already_analyzed`, or error

#### 2. Fixed Analysis Summary Query (`backend/app/api/analysis.py`)
- Modified to return ALL analyzed games if none found in the specified date range
- Prevents empty results when games are older than 7 days
- Logs when using all games instead of recent ones

#### 3. Fixed User Creation (`backend/app/api/users.py`)
- Added error handling for duplicate email constraint
- Returns existing user if duplicate found
- Prevents application crash on user re-creation

### Frontend Changes

#### 1. API Client (`frontend/src/lib/api.ts`)
- Added `analyzeSingleGame()` method
- Calls new backend endpoint for individual game analysis

#### 2. Dashboard Component (`frontend/src/pages/dashboard.tsx`)

**State Management:**
- Added `analyzingGameIds` Set to track games being analyzed
- Prevents duplicate analysis requests

**Individual Analyze Button:**
- Purple "Analyze" button with ⚡ icon for each unanalyzed game
- Shows "Analyzing..." with spinner during analysis
- Shows "✓ Analyzed" badge when complete

**Real-time Updates:**
- Polls every 3 seconds for up to 3 minutes
- Automatically refetches games, user data, and analysis summary
- Second refetch after 2 seconds to ensure database commit
- Console logging for debugging

**ACPL Chart Improvements:**
- Added "🔄 Refresh" button for manual refresh
- Better empty state messaging
- Shows chart only when games are analyzed
- Improved tooltip and Y-axis labeling

**Query Configuration:**
- Set `staleTime: 0` and `cacheTime: 0` for fresh data
- Enabled `refetchOnWindowFocus` and `refetchOnMount`
- Added console logging to track data fetching

## How to Test

### 1. Restart Backend
```bash
cd e:\chess\chess-AI\backend
python -m uvicorn app.__main__:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO: Application startup complete.
⚠️ Redis not available: ... Using mock client
CORS enabled for origins: ['http://localhost:3000', ...]
```

### 2. Refresh Frontend
- Open browser to `http://localhost:3000`
- Hard refresh (Ctrl+Shift+R) to clear cache
- Navigate to your dashboard

### 3. Test Individual Game Analysis

**Step 1: Click Analyze Button**
- Find an unanalyzed game in the "Fetched Games" section
- Click the purple "Analyze" button
- Button should change to "Analyzing..." with spinner

**Step 2: Watch Backend Logs**
Look for these messages in the backend terminal:
```
🔍 Starting Stockfish analysis for game X
🧠 Analyzing game X with UnifiedChessAnalyzer (depth=15)...
✅ Game X analyzed successfully: ACPL=XX.X, Accuracy=XX.X%, Blunders=X, Mistakes=X
```

**Step 3: Watch Frontend Console**
Open browser DevTools (F12) and look for:
```
🔄 Refetching all data after analysis completion...
📊 Analysis Summary after refetch: {total_games_analyzed: 1, ...}
🎮 Games after refetch: 1 analyzed
🔄 Second refetch to ensure data is updated...
📊 Fetched analysis summary: {total_games_analyzed: 1, ...}
```

**Step 4: Verify UI Updates**
After ~10-30 seconds, you should see:
- ✅ Success toast: "Game analysis complete! Dashboard updating..."
- Game badge changes to "✓ Analyzed" (green)
- "Games Analyzed" count increases
- ACPL chart appears with data
- Average Accuracy updates
- Phase Performance chart shows bars

### 4. Manual Refresh (If Needed)
If the UI doesn't update automatically:
- Click the "🔄 Refresh" button on the ACPL chart
- Check browser console for the logged data
- Verify backend shows successful analysis

## Troubleshooting

### Issue: "No analyzed games found for this period"
**Cause:** Games are older than 7 days
**Solution:** Backend now automatically includes all games if none in period

### Issue: UI not updating after analysis
**Cause:** Query cache or timing issue
**Solution:** 
1. Click "🔄 Refresh" button
2. Check console logs for refetch data
3. Verify backend logs show successful analysis
4. Hard refresh browser (Ctrl+Shift+R)

### Issue: Backend crashes on user creation
**Cause:** Duplicate email constraint
**Solution:** Backend now handles duplicates gracefully

### Issue: Analysis takes too long
**Cause:** Stockfish processing complex game
**Solution:** Wait up to 3 minutes, or check backend logs for errors

## Expected Analysis Times
- Simple games (20-30 moves): 10-15 seconds
- Average games (40-60 moves): 20-30 seconds
- Complex games (80+ moves): 30-60 seconds

## Console Debugging Commands

### Check if analysis is saved:
```sql
SELECT g.id, g.is_analyzed, a.user_acpl, a.accuracy_percentage
FROM games g
LEFT JOIN game_analyses a ON g.id = a.game_id
WHERE g.user_id = 1
ORDER BY g.created_at DESC;
```

### Force refresh analysis summary:
```javascript
// In browser console
window.location.reload(true);
```

## Key Features
✅ Individual game analysis (not just batch)
✅ Real-time UI updates during analysis
✅ Visual feedback (spinner, badges, toasts)
✅ Automatic dashboard refresh
✅ Manual refresh option
✅ Error handling and recovery
✅ Console logging for debugging
✅ Works with older games (not just last 7 days)

## Next Steps
1. Restart backend
2. Refresh frontend
3. Analyze a game
4. Watch the magic happen! 🎉
