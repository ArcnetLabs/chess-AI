# Accessing Game Analysis Data

## Overview
This document explains how users can access and view game analysis data (`game_analyses`) in the Chess AI application. Analysis data includes move classifications, ACPL metrics, accuracy percentages, and phase-based performance.

---

## Table of Contents
1. [Dashboard UI Access](#1-dashboard-ui-access-primary-method)
2. [API Endpoints](#2-api-endpoints-programmatic-access)
3. [Database Direct Access](#3-database-direct-access)
4. [Data Schema Reference](#4-data-schema-reference)
5. [Common Use Cases](#5-common-use-cases)
6. [Future Enhancements](#6-future-enhancements)

---

## 1. Dashboard UI Access (Primary Method)

### Accessing the Dashboard
**URL**: `http://localhost:3000/dashboard?username=<your_chesscom_username>`

**Example**: `http://localhost:3000/dashboard?username=i_rat_007`

### Available Analysis Views

#### A. Performance Overview Cards
Located at the top of the dashboard, displays:

| Card | Description | Data Source |
|------|-------------|-------------|
| **Games Analyzed** | Total number of analyzed games | `game_analyses.id` count |
| **Average Accuracy** | Overall accuracy percentage (0-100%) | Average of `game_analyses.accuracy_percentage` |
| **ACPL** | Average Centipawn Loss (lower is better) | Average of `game_analyses.user_acpl` |
| **Favorite Opening** | Most frequently played opening | `game_analyses.opening_name` |

#### B. Move Quality Breakdown Chart
Visual bar/pie chart showing distribution of move classifications:

- **Brilliant Moves**: Exceptional moves (sacrifices, tactical brilliancies)
- **Great Moves**: Very strong moves
- **Best Moves**: Engine's top choice
- **Excellent Moves**: Near-optimal moves
- **Good Moves**: Reasonable moves
- **Inaccuracies**: Minor errors (≥100cp loss)
- **Mistakes**: Significant errors (≥200cp loss)
- **Blunders**: Major blunders (≥300cp loss)

**Data Source**: Aggregated from all analyzed games' move classification counts

#### C. Phase Performance Chart
ACPL breakdown by game phase:

| Phase | Description | Data Field |
|-------|-------------|------------|
| **Opening** | First 10-15 moves | `game_analyses.opening_acpl` |
| **Middlegame** | Middle portion of game | `game_analyses.middlegame_acpl` |
| **Endgame** | Final phase | `game_analyses.endgame_acpl` |

**Interpretation**: Lower ACPL = Better performance in that phase

#### D. Individual Game Status
In the "Fetched Games" section, each game shows:

- **✓ Analyzed** (Green badge): Game has been analyzed
- **Analyze** (Purple button): Click to analyze this game
- **Analyzing...** (Blue badge): Analysis in progress

#### E. Manual Refresh
- **🔄 Refresh button**: Located on the ACPL chart for manual data refresh
- Auto-refresh happens after each game analysis completes

---

## 2. API Endpoints (Programmatic Access)

### Base URL
```
http://localhost:8000/api/v1
```

### A. Get Analysis Summary
**Endpoint**: `GET /analysis/{user_id}/summary`

**Query Parameters**:
- `days` (optional): Number of days to look back (default: 7)

**Example Request**:
```bash
curl http://localhost:8000/api/v1/analysis/1/summary?days=7
```

**Example Response**:
```json
{
  "period_days": 7,
  "total_games_analyzed": 15,
  "average_acpl": 45.3,
  "accuracy_percentage": 87.5,
  "move_quality_breakdown": {
    "brilliant_moves": 2,
    "great_moves": 8,
    "best_moves": 45,
    "excellent_moves": 67,
    "good_moves": 89,
    "inaccuracies": 23,
    "mistakes": 12,
    "blunders": 4
  },
  "phase_performance": {
    "opening_acpl": 35.2,
    "middlegame_acpl": 48.7,
    "endgame_acpl": 52.1
  },
  "most_played_openings": [
    ["Italian Game", 5],
    ["Sicilian Defense", 4],
    ["Queen's Gambit", 3]
  ]
}
```

### B. Get Single Game Analysis
**Endpoint**: `GET /analysis/{user_id}/games/{game_id}/analysis`

**Example Request**:
```bash
curl http://localhost:8000/api/v1/analysis/1/games/123/analysis
```

**Example Response**:
```json
{
  "game_id": 123,
  "user_color": "white",
  "user_acpl": 42.5,
  "opponent_acpl": 55.3,
  "accuracy_percentage": 88.2,
  "brilliant_moves": 1,
  "great_moves": 3,
  "best_moves": 15,
  "excellent_moves": 20,
  "good_moves": 25,
  "inaccuracies": 8,
  "mistakes": 3,
  "blunders": 1,
  "opening_name": "Italian Game",
  "opening_eco": "C50",
  "opening_acpl": 30.5,
  "middlegame_acpl": 45.2,
  "endgame_acpl": 50.8,
  "engine_version": "Stockfish 16",
  "analysis_depth": 15
}
```

### C. Analyze Single Game
**Endpoint**: `POST /analysis/{user_id}/analyze/{game_id}`

**Query Parameters**:
- `force_reanalysis` (optional): Re-analyze even if already analyzed (default: false)

**Example Request**:
```bash
curl -X POST http://localhost:8000/api/v1/analysis/1/analyze/123
```

**Example Response**:
```json
{
  "status": "queued",
  "message": "Analysis started",
  "game_id": 123,
  "games_queued": 1
}
```

### D. Analyze All Games
**Endpoint**: `POST /analysis/{user_id}/analyze`

**Request Body**:
```json
{
  "days": 365,
  "force_reanalysis": false
}
```

**Example Request**:
```bash
curl -X POST http://localhost:8000/api/v1/analysis/1/analyze \
  -H "Content-Type: application/json" \
  -d '{"days": 365, "force_reanalysis": false}'
```

**Example Response**:
```json
{
  "status": "queued",
  "message": "Analysis started for 25 games",
  "games_queued": 25
}
```

### E. Get All Games (with analysis status)
**Endpoint**: `GET /games/{user_id}`

**Query Parameters**:
- `limit` (optional): Max number of games to return (default: 100)

**Example Request**:
```bash
curl http://localhost:8000/api/v1/games/1?limit=100
```

**Response includes `is_analyzed` field for each game**

---

## 3. Database Direct Access

### Database Location
```
e:\chess\chess-AI\backend\chess_ai.db
```

### Accessing the Database

#### Using SQLite CLI
```bash
cd e:\chess\chess-AI\backend
sqlite3 chess_ai.db
```

#### Using Python
```python
import sqlite3

conn = sqlite3.connect('e:/chess/chess-AI/backend/chess_ai.db')
cursor = conn.cursor()

# Your queries here
cursor.execute("SELECT * FROM game_analyses LIMIT 10")
results = cursor.fetchall()

conn.close()
```

### Common SQL Queries

#### 1. View All Analyses for a User
```sql
SELECT 
    ga.id,
    ga.game_id,
    g.white_username,
    g.black_username,
    g.time_class,
    ga.user_color,
    ga.user_acpl,
    ga.accuracy_percentage,
    ga.brilliant_moves,
    ga.great_moves,
    ga.best_moves,
    ga.excellent_moves,
    ga.good_moves,
    ga.inaccuracies,
    ga.mistakes,
    ga.blunders,
    ga.opening_name,
    ga.opening_eco,
    ga.created_at
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1
ORDER BY ga.created_at DESC;
```

#### 2. Get Summary Statistics
```sql
SELECT 
    COUNT(*) as total_analyzed,
    AVG(user_acpl) as avg_acpl,
    AVG(accuracy_percentage) as avg_accuracy,
    SUM(brilliant_moves) as total_brilliant,
    SUM(great_moves) as total_great,
    SUM(best_moves) as total_best,
    SUM(excellent_moves) as total_excellent,
    SUM(good_moves) as total_good,
    SUM(inaccuracies) as total_inaccuracies,
    SUM(mistakes) as total_mistakes,
    SUM(blunders) as total_blunders
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1;
```

#### 3. Find Games with Most Blunders
```sql
SELECT 
    g.id,
    g.white_username,
    g.black_username,
    g.chesscom_url,
    ga.blunders,
    ga.mistakes,
    ga.user_acpl,
    ga.accuracy_percentage
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1
ORDER BY ga.blunders DESC, ga.mistakes DESC
LIMIT 10;
```

#### 4. Opening Performance Analysis
```sql
SELECT 
    ga.opening_name,
    COUNT(*) as games_played,
    AVG(ga.user_acpl) as avg_acpl,
    AVG(ga.accuracy_percentage) as avg_accuracy,
    AVG(ga.opening_acpl) as avg_opening_acpl
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1 AND ga.opening_name IS NOT NULL
GROUP BY ga.opening_name
ORDER BY games_played DESC
LIMIT 10;
```

#### 5. Phase Performance Comparison
```sql
SELECT 
    AVG(opening_acpl) as avg_opening_acpl,
    AVG(middlegame_acpl) as avg_middlegame_acpl,
    AVG(endgame_acpl) as avg_endgame_acpl
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1;
```

#### 6. Best and Worst Games
```sql
-- Best games (lowest ACPL)
SELECT 
    g.id,
    g.white_username,
    g.black_username,
    ga.user_acpl,
    ga.accuracy_percentage,
    g.chesscom_url
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1
ORDER BY ga.user_acpl ASC
LIMIT 5;

-- Worst games (highest ACPL)
SELECT 
    g.id,
    g.white_username,
    g.black_username,
    ga.user_acpl,
    ga.accuracy_percentage,
    g.chesscom_url
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1
ORDER BY ga.user_acpl DESC
LIMIT 5;
```

---

## 4. Data Schema Reference

### `game_analyses` Table Structure

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `game_id` | INTEGER | Foreign key to `games.id` (unique) |
| `created_at` | DATETIME | When analysis was created |
| `updated_at` | DATETIME | Last update timestamp |
| **Analysis Metadata** | | |
| `engine_version` | STRING | Stockfish version used |
| `analysis_depth` | INTEGER | Search depth (default: 15) |
| `analysis_time` | FLOAT | Time spent analyzing (seconds) |
| **User Metrics** | | |
| `user_color` | STRING | "white" or "black" |
| `user_acpl` | FLOAT | User's Average Centipawn Loss |
| `opponent_acpl` | FLOAT | Opponent's ACPL |
| `accuracy_percentage` | FLOAT | User's accuracy (0-100) |
| **Move Classifications** | | |
| `brilliant_moves` | INTEGER | Count of brilliant moves |
| `great_moves` | INTEGER | Count of great moves |
| `best_moves` | INTEGER | Count of best moves |
| `excellent_moves` | INTEGER | Count of excellent moves |
| `good_moves` | INTEGER | Count of good moves |
| `inaccuracies` | INTEGER | Count of inaccuracies |
| `mistakes` | INTEGER | Count of mistakes |
| `blunders` | INTEGER | Count of blunders |
| **Phase Analysis** | | |
| `opening_acpl` | FLOAT | ACPL during opening phase |
| `middlegame_acpl` | FLOAT | ACPL during middlegame |
| `endgame_acpl` | FLOAT | ACPL during endgame |
| **Opening Analysis** | | |
| `opening_name` | STRING | Opening name (e.g., "Italian Game") |
| `opening_eco` | STRING | ECO code (e.g., "C50") |
| `opening_moves` | INTEGER | Number of opening moves |
| **Detailed Data (JSON)** | | |
| `evaluations` | JSON | Move-by-move evaluations array |
| `critical_positions` | JSON | Key positions with eval swings |
| `blunder_moves` | JSON | Detailed blunder information |

### Move Classification Thresholds

| Classification | Centipawn Loss | Description |
|---------------|----------------|-------------|
| **Brilliant** | < -50cp | Exceptional move (sacrifice, etc.) |
| **Great** | -50 to -25cp | Very strong move |
| **Best** | 0cp | Engine's top choice |
| **Excellent** | 0 to 25cp | Near-optimal move |
| **Good** | 25 to 50cp | Reasonable move |
| **Inaccuracy** | 50 to 100cp | Minor error |
| **Mistake** | 100 to 200cp | Significant error |
| **Blunder** | > 200cp | Major blunder |

### ACPL to Accuracy Conversion

The system uses a piecewise linear mapping:

| ACPL Range | Accuracy Range |
|------------|----------------|
| 0-10 | 95-100% |
| 10-20 | 90-95% |
| 20-30 | 85-90% |
| 30-50 | 75-85% |
| 50-100 | 50-75% |
| 100+ | 0-50% |

---

## 5. Common Use Cases

### Use Case 1: View My Overall Performance
**Method**: Dashboard UI
1. Navigate to `http://localhost:3000/dashboard?username=<your_username>`
2. View Performance Overview Cards for quick stats
3. Check Move Quality Breakdown chart for move distribution
4. Review Phase Performance chart to identify weak phases

### Use Case 2: Analyze a Specific Game
**Method**: Dashboard UI
1. Go to dashboard
2. Scroll to "Fetched Games" section
3. Find the game you want to analyze
4. Click the purple "Analyze" button
5. Wait 10-30 seconds for analysis to complete
6. Game badge will change to "✓ Analyzed"
7. Dashboard metrics will update automatically

### Use Case 3: Analyze All My Games at Once
**Method**: Dashboard UI
1. Go to dashboard
2. Click the green "Analyze with AI" button at the top
3. Wait for batch analysis to complete (polls every 3 seconds)
4. Watch games turn green one by one as they complete
5. Dashboard updates in real-time

### Use Case 4: Export Analysis Data for External Tools
**Method**: API + Script
```python
import requests
import json

# Get analysis summary
response = requests.get('http://localhost:8000/api/v1/analysis/1/summary?days=30')
data = response.json()

# Save to file
with open('my_analysis.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Exported analysis for {data['total_games_analyzed']} games")
```

### Use Case 5: Find My Weakest Opening
**Method**: Database Query
```sql
SELECT 
    opening_name,
    COUNT(*) as games,
    AVG(user_acpl) as avg_acpl,
    AVG(accuracy_percentage) as avg_accuracy
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1 AND opening_name IS NOT NULL
GROUP BY opening_name
HAVING COUNT(*) >= 3  -- At least 3 games
ORDER BY avg_acpl DESC  -- Highest ACPL = weakest
LIMIT 5;
```

### Use Case 6: Track Improvement Over Time
**Method**: Database Query
```sql
SELECT 
    DATE(ga.created_at) as analysis_date,
    COUNT(*) as games_analyzed,
    AVG(ga.user_acpl) as avg_acpl,
    AVG(ga.accuracy_percentage) as avg_accuracy
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1
GROUP BY DATE(ga.created_at)
ORDER BY analysis_date DESC
LIMIT 30;
```

### Use Case 7: Identify Games to Review
**Method**: Database Query
```sql
-- Games with most blunders (need review)
SELECT 
    g.id,
    g.chesscom_url,
    ga.blunders,
    ga.mistakes,
    ga.user_acpl
FROM game_analyses ga
JOIN games g ON ga.game_id = g.id
WHERE g.user_id = 1 AND ga.blunders > 0
ORDER BY ga.blunders DESC, ga.mistakes DESC
LIMIT 10;
```

---

## 6. Future Enhancements

### Planned Features (Not Yet Implemented)

#### A. Individual Game Analysis Page
**Proposed URL**: `/game/{game_id}/analysis`

**Would Include**:
- Move-by-move breakdown with evaluation graph
- Interactive chessboard showing position at each move
- Critical positions highlighted
- Detailed blunder analysis with alternative moves
- Opening analysis and comparison to theory
- Downloadable analysis report

#### B. Advanced Filtering
- Filter games by time control
- Filter by opening
- Filter by date range
- Filter by result (win/loss/draw)
- Filter by opponent rating range

#### C. Comparison Features
- Compare performance across different openings
- Compare performance vs different opponents
- Compare performance in different time controls
- Track improvement trends over time

#### D. AI Coaching Recommendations
- Personalized training suggestions based on weakest areas
- Opening repertoire recommendations
- Tactical pattern identification
- Endgame weakness detection

#### E. Export Features
- Export to PGN with annotations
- Export to PDF report
- Export to CSV for spreadsheet analysis
- Integration with chess.com analysis board

---

## 7. Troubleshooting

### Issue: Dashboard shows 0 games analyzed
**Solution**:
1. Check if games have been fetched (click "Sync Recent Games")
2. Click "Analyze with AI" to start analysis
3. Wait for analysis to complete (10-30 seconds per game)
4. Click "🔄 Refresh" button on ACPL chart if needed

### Issue: Analysis not updating after clicking Analyze
**Solution**:
1. Check backend logs for Stockfish errors
2. Verify backend is running (`http://localhost:8000/docs`)
3. Hard refresh browser (Ctrl+Shift+R)
4. Check browser console for errors (F12)

### Issue: Cannot access API endpoints
**Solution**:
1. Ensure backend is running on port 8000
2. Check CORS settings in backend
3. Verify user_id is correct
4. Check API documentation at `http://localhost:8000/docs`

### Issue: Database query returns no results
**Solution**:
1. Verify user_id is correct
2. Check if games have been analyzed (`is_analyzed = true`)
3. Ensure database path is correct
4. Run `SELECT COUNT(*) FROM game_analyses;` to verify data exists

---

## 8. Additional Resources

### Related Documentation
- [Stockfish Integration Guide](./backend/STOCKFISH_INTEGRATION_COMPLETE.md)
- [Individual Game Analysis Implementation](./INDIVIDUAL_GAME_ANALYSIS_IMPLEMENTATION.md)
- [Analyze All Games Feature](./ANALYZE_ALL_GAMES_FEATURE.md)

### API Documentation
- Interactive API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Database Tools
- SQLite Browser: https://sqlitebrowser.org/
- DBeaver: https://dbeaver.io/

### Support
- Check backend logs: `e:\chess\chess-AI\backend\` (console output)
- Check browser console: F12 → Console tab
- Review error messages in toast notifications

---

## Summary

Users can access game analysis data through:

1. **Dashboard UI** (Primary) - Visual charts and metrics
2. **API Endpoints** - Programmatic access for integrations
3. **Database Queries** - Direct SQL access for advanced analysis

All analysis data is stored in the `game_analyses` table and includes:
- Move classifications (brilliant → blunder)
- ACPL and accuracy metrics
- Phase-based performance (opening/middlegame/endgame)
- Opening analysis

The system provides real-time updates as games are analyzed, with automatic dashboard refresh and incremental metric updates.
