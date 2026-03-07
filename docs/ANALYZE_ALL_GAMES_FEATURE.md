# Analyze All Games Feature

## Overview
The "Analyze All Games" button allows you to analyze all fetched games at once, rather than analyzing them one by one.

## Changes Made

### Backend (`backend/app/api/analysis.py`)
- Modified the `analyze_user_games` endpoint to analyze **ALL games** for a user
- Removed the 7-day date filter that was limiting analysis to recent games only
- Now queries all games in the database for the user
- Still respects the `force_reanalysis` flag to skip already-analyzed games

### Frontend (`frontend/src/pages/dashboard.tsx`)
- Updated `handleAnalyzeGames` to use `days: 365` to ensure all games are included
- The button is located in the action buttons section at the top of the dashboard

## How It Works

### 1. Button Location
The "Analyze All Games" button is in the top action buttons section:
```
[Sync Recent Games] [Analyze with AI] [Force Re-analyze]
```

### 2. Button States
- **Enabled**: Shows "Analyze with AI" when there are unanalyzed games
- **Disabled**: Shows "All Analyzed" when all games are already analyzed
- **Analyzing**: Shows "Analyzing..." with spinner during analysis

### 3. Analysis Process
1. User clicks "Analyze with AI"
2. Backend queries ALL games for the user
3. Filters out already-analyzed games (unless force_reanalysis is true)
4. Queues each game for background analysis with Stockfish
5. Frontend polls every 5 seconds to check progress
6. Dashboard updates automatically when all games are analyzed

### 4. Backend Logic
```python
# Get ALL games for the user (not filtered by date)
games_query = db.query(Game).filter(
    Game.user_id == user_id
)

# Filter out already analyzed games
if not request.force_reanalysis:
    games_query = games_query.filter(Game.is_analyzed == False)

games_to_analyze = games_query.all()
```

### 5. Frontend Logic
```typescript
const handleAnalyzeGames = async (forceReanalysis = false) => {
  const result = await api.analysis.analyzeGames(user.id, { 
    days: 365, // Large number to include all games
    forceReanalysis 
  });
  
  if (result.games_queued > 0) {
    // Start polling for completion
    startAnalysisPolling();
  }
};
```

## Usage

### Analyze All Unanalyzed Games
1. Click the **"Analyze with AI"** button
2. Wait for analysis to complete (progress shown in modal)
3. Dashboard updates automatically

### Force Re-analyze All Games
1. Click the **"Force Re-analyze"** button (only visible if games are already analyzed)
2. Confirms you want to re-analyze all games
3. Re-analyzes even already-analyzed games

### Analyze Individual Game
1. Scroll to the "Fetched Games" section
2. Find an unanalyzed game
3. Click the purple **"Analyze"** button on that specific game
4. Dashboard updates when that game completes

## Expected Behavior

### Small Game Collection (1-10 games)
- Analysis completes in 1-5 minutes
- Dashboard updates automatically
- All metrics populate (ACPL, accuracy, phase performance)

### Medium Game Collection (11-50 games)
- Analysis completes in 5-20 minutes
- Progress shown in modal
- Dashboard updates incrementally as games complete

### Large Game Collection (50+ games)
- Analysis may take 20+ minutes
- Consider analyzing in batches using individual game buttons
- Dashboard updates as each game completes

## Monitoring Progress

### Backend Logs
Watch for these messages:
```
🔍 Starting Stockfish analysis for game X
🧠 Analyzing game X with UnifiedChessAnalyzer (depth=15)...
✅ Game X analyzed successfully: ACPL=XX.X, Accuracy=XX.X%
```

### Frontend Console
Watch for these messages:
```
🔄 Refetching all data after analysis completion...
📊 Analysis Summary after refetch: {total_games_analyzed: X, ...}
🎮 Games after refetch: X analyzed
```

### Dashboard UI
- "Games Analyzed" count increases
- ACPL chart appears with data
- Average Accuracy updates
- Phase Performance chart shows bars
- Individual game badges change to "✓ Analyzed"

## Troubleshooting

### Issue: Button says "All Analyzed" but games show "Not analyzed"
**Solution:** 
- Refresh the page (Ctrl+R)
- Click "🔄 Refresh" on ACPL chart
- Check backend logs for analysis errors

### Issue: Analysis takes too long
**Solution:**
- Use individual game analysis instead
- Check backend logs for Stockfish errors
- Ensure Stockfish binary is accessible

### Issue: Dashboard doesn't update after analysis
**Solution:**
- Click "🔄 Refresh" button on ACPL chart
- Check browser console for errors
- Verify backend shows successful analysis
- Hard refresh browser (Ctrl+Shift+R)

## Performance Tips

1. **Analyze in batches**: Use individual game buttons for large collections
2. **Monitor backend**: Watch logs to ensure Stockfish is running
3. **Be patient**: Complex games take longer to analyze
4. **Use Force Re-analyze sparingly**: Only when you need fresh analysis

## Technical Details

### Analysis Queue
- Each game is queued as a background task
- Stockfish analyzes games sequentially
- Database commits after each game completes

### Polling Strategy
- Frontend polls every 5 seconds
- Checks analyzed game count
- Stops after 2.5 minutes or when all games complete
- Refetches all dashboard data on completion

### Data Flow
```
User clicks button
  → Frontend calls /api/v1/analysis/{user_id}/analyze
  → Backend queries all unanalyzed games
  → Backend queues background tasks
  → Stockfish analyzes each game
  → Database saves analysis results
  → Frontend polls for completion
  → Dashboard updates automatically
```

## Next Steps
1. Restart backend to load changes
2. Refresh frontend
3. Click "Analyze with AI" to analyze all games
4. Watch the magic happen! 🎉
