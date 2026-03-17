# 🚀 How to Use Stockfish Analysis in Your Application

## Quick Start Guide

### ✅ Prerequisites
- [x] Stockfish binary installed (`backend/stockfish/stockfish.exe`)
- [x] Backend running (`python -m app`)
- [x] Database configured (Supabase)
- [x] User created with Chess.com username

---

## 📋 Step-by-Step Usage

### **Step 1: Register the New Analysis API**

Update `backend/app/__main__.py` to include the new Stockfish analysis router:

```python
from app.api import analysis_stockfish

# Add this line with other router includes
app.include_router(
    analysis_stockfish.router,
    prefix="/api/analysis",
    tags=["analysis"]
)
```

### **Step 2: Fetch Games from Chess.com**

```bash
# Example: Fetch games for user ID 1
curl -X POST http://localhost:8000/api/games/1/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "months": ["2024/12"],
    "time_classes": ["rapid", "blitz"]
  }'
```

**Response:**
```json
{
  "status": "success",
  "games_fetched": 25,
  "games_stored": 25
}
```

### **Step 3: Analyze Games with Stockfish**

```bash
# Analyze up to 10 recent games
curl -X POST http://localhost:8000/api/analysis/1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "max_games": 10,
    "force_reanalysis": false
  }'
```

**Response:**
```json
{
  "status": "queued",
  "games_queued": 10,
  "message": "Analyzing 10 games in background. Check back in a few minutes."
}
```

**What Happens:**
- Games are queued for background analysis
- Each game takes ~1-2 minutes to analyze
- Results are saved to database automatically
- You can continue using the app while analysis runs

### **Step 4: Check Analysis Results**

```bash
# Get analysis for a specific game (game_id = 123)
curl http://localhost:8000/api/analysis/1/games/123/analysis
```

**Response:**
```json
{
  "id": 1,
  "game_id": 123,
  "user_color": "white",
  "user_acpl": 25.3,
  "opponent_acpl": 42.1,
  "accuracy_percentage": 87.5,
  "brilliant_moves": 0,
  "best_moves": 15,
  "good_moves": 8,
  "inaccuracies": 3,
  "mistakes": 2,
  "blunders": 1,
  "opening_acpl": 18.2,
  "middlegame_acpl": 28.5,
  "endgame_acpl": 31.0,
  "opening_name": "Sicilian Defense",
  "opening_eco": "B20",
  "engine_version": "Stockfish 17",
  "analysis_depth": 15,
  "analyzed_at": "2024-12-19T12:00:00Z"
}
```

### **Step 5: Get Summary Statistics**

```bash
# Get summary for last 30 days
curl http://localhost:8000/api/analysis/1/summary?days=30
```

**Response:**
```json
{
  "status": "success",
  "period_days": 30,
  "total_games": 25,
  "overall": {
    "average_acpl": 28.5,
    "average_accuracy": 85.2,
    "total_blunders": 12,
    "total_mistakes": 28,
    "total_inaccuracies": 45,
    "total_best_moves": 320,
    "blunders_per_game": 0.5,
    "mistakes_per_game": 1.1
  },
  "phase_analysis": {
    "opening": {
      "average_acpl": 22.3,
      "games_analyzed": 25
    },
    "middlegame": {
      "average_acpl": 30.8,
      "games_analyzed": 25
    },
    "endgame": {
      "average_acpl": 35.2,
      "games_analyzed": 18
    }
  }
}
```

---

## 💻 Frontend Integration

### **React Component Example**

```typescript
// components/GameAnalysis.tsx
import { useState, useEffect } from 'react';

interface AnalysisData {
  user_acpl: number;
  accuracy_percentage: number;
  blunders: number;
  mistakes: number;
  inaccuracies: number;
  opening_name: string;
}

export function GameAnalysis({ gameId, userId }: { gameId: number; userId: number }) {
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`http://localhost:8000/api/analysis/${userId}/games/${gameId}/analysis`)
      .then(res => res.json())
      .then(data => {
        setAnalysis(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch analysis:', err);
        setLoading(false);
      });
  }, [gameId, userId]);

  if (loading) return <div>Loading analysis...</div>;
  if (!analysis) return <div>No analysis available</div>;

  return (
    <div className="analysis-card">
      <h3>Game Analysis</h3>
      
      <div className="metrics">
        <div className="metric">
          <label>Accuracy</label>
          <span className="value">{analysis.accuracy_percentage.toFixed(1)}%</span>
        </div>
        
        <div className="metric">
          <label>ACPL</label>
          <span className="value">{analysis.user_acpl.toFixed(1)}</span>
        </div>
      </div>

      <div className="move-quality">
        <h4>Move Quality</h4>
        <div className="quality-bar">
          <div className="blunders" style={{ width: `${analysis.blunders * 10}%` }}>
            {analysis.blunders} Blunders
          </div>
          <div className="mistakes" style={{ width: `${analysis.mistakes * 10}%` }}>
            {analysis.mistakes} Mistakes
          </div>
          <div className="inaccuracies" style={{ width: `${analysis.inaccuracies * 10}%` }}>
            {analysis.inaccuracies} Inaccuracies
          </div>
        </div>
      </div>

      <div className="opening-info">
        <label>Opening:</label>
        <span>{analysis.opening_name}</span>
      </div>
    </div>
  );
}
```

### **Analyze Button Component**

```typescript
// components/AnalyzeButton.tsx
import { useState } from 'react';

export function AnalyzeButton({ userId }: { userId: number }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setResult(null);

    try {
      const response = await fetch(`http://localhost:8000/api/analysis/${userId}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_games: 10,
          force_reanalysis: false
        })
      });

      const data = await response.json();
      setResult(`${data.games_queued} games queued for analysis`);
    } catch (err) {
      setResult('Failed to queue analysis');
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div>
      <button 
        onClick={handleAnalyze} 
        disabled={analyzing}
        className="analyze-btn"
      >
        {analyzing ? 'Queueing...' : 'Analyze Games'}
      </button>
      {result && <p className="result-message">{result}</p>}
    </div>
  );
}
```

---

## 🧪 Testing the Integration

### **1. Test Engine Directly**

```bash
cd backend
python tests/test_stockfish_engine.py
```

### **2. Test Game Analysis**

```bash
cd backend
python test_game_analysis.py
```

### **3. Test API Endpoints**

```bash
# Start backend
cd backend
python -m app

# In another terminal, test endpoints
# 1. Fetch games
curl -X POST http://localhost:8000/api/games/1/fetch -H "Content-Type: application/json" -d '{"months": ["2024/12"]}'

# 2. Analyze games
curl -X POST http://localhost:8000/api/analysis/1/analyze -H "Content-Type: application/json" -d '{"max_games": 5}'

# 3. Wait 2-3 minutes for analysis to complete

# 4. Check results
curl http://localhost:8000/api/analysis/1/summary?days=30
```

---

## 📊 Understanding the Results

### **ACPL (Average Centipawn Loss)**

| ACPL Range | Skill Level | Description |
|------------|-------------|-------------|
| < 10 | Grandmaster | Near-perfect play |
| 10-20 | Master | Very strong play |
| 20-50 | Expert | Good play with minor errors |
| 50-100 | Intermediate | Noticeable mistakes |
| > 100 | Beginner | Frequent errors |

### **Accuracy Percentage**

| Accuracy | Rating |
|----------|--------|
| 95-100% | Excellent |
| 85-95% | Good |
| 70-85% | Average |
| < 70% | Needs Improvement |

### **Move Classifications**

- **Brilliant**: Exceptional move (rare)
- **Best**: Engine's top choice
- **Good**: Reasonable move (< 50 cp loss)
- **Inaccuracy**: Minor error (50-100 cp loss)
- **Mistake**: Significant error (100-200 cp loss)
- **Blunder**: Major error (> 200 cp loss)

---

## 🎯 Common Use Cases

### **1. Analyze Recent Games**

```python
# Analyze last 10 games
POST /api/analysis/{user_id}/analyze
{
  "max_games": 10
}
```

### **2. Re-analyze Specific Games**

```python
# Re-analyze specific games with fresh analysis
POST /api/analysis/{user_id}/analyze
{
  "game_ids": [123, 124, 125],
  "force_reanalysis": true
}
```

### **3. Track Improvement Over Time**

```python
# Get monthly summaries
GET /api/analysis/{user_id}/summary?days=30  # Last month
GET /api/analysis/{user_id}/summary?days=60  # Last 2 months
GET /api/analysis/{user_id}/summary?days=90  # Last 3 months
```

### **4. Identify Weaknesses**

```python
# Get detailed analysis
GET /api/analysis/{user_id}/games/{game_id}/analysis

# Check phase_analysis to see:
# - opening_acpl: How well you play openings
# - middlegame_acpl: Tactical/strategic play
# - endgame_acpl: Endgame technique
```

---

## ⚡ Performance Tips

### **Batch Analysis**

```python
# Analyze in batches to avoid overload
# Good: Analyze 10 games at a time
POST /api/analysis/{user_id}/analyze {"max_games": 10}

# Bad: Analyze 100 games at once (will take hours)
POST /api/analysis/{user_id}/analyze {"max_games": 100}
```

### **Analysis Speed**

- **Single game**: ~1-2 minutes (depth 15)
- **10 games**: ~10-20 minutes
- **Faster analysis**: Reduce depth to 10 (less accurate)
- **Better analysis**: Increase depth to 20 (slower)

### **Configure in `.env`**

```env
STOCKFISH_DEPTH=15      # Balance of speed and accuracy
STOCKFISH_TIME=1.0      # 1 second per position
STOCKFISH_THREADS=2     # Use 2 CPU cores
STOCKFISH_HASH=256      # 256 MB memory
```

---

## 🐛 Troubleshooting

### **"Analysis not found"**

**Problem**: Game hasn't been analyzed yet  
**Solution**: Queue the game for analysis first

```bash
curl -X POST http://localhost:8000/api/analysis/1/analyze \
  -H "Content-Type: application/json" \
  -d '{"game_ids": [123]}'
```

### **"Stockfish binary not found"**

**Problem**: Stockfish not installed  
**Solution**: Download and place in `backend/stockfish/stockfish.exe`

See: `STOCKFISH_SETUP.md`

### **Analysis is slow**

**Problem**: High depth or many games  
**Solution**: Reduce depth or analyze fewer games at once

```env
STOCKFISH_DEPTH=10  # Faster but less accurate
```

---

## 📚 Additional Resources

- **Setup Guide**: `STOCKFISH_SETUP.md`
- **Working Guide**: `STOCKFISH_WORKING_GUIDE.md`
- **Integration Complete**: `STOCKFISH_INTEGRATION_COMPLETE.md`
- **API Code**: `app/api/analysis_stockfish.py`
- **Engine Code**: `app/services/engine/stockfish_engine.py`
- **Analyzer Code**: `app/services/analysis/unified_analyzer.py`

---

## ✅ Summary

**To use Stockfish in your app:**

1. ✅ **Register API**: Add `analysis_stockfish` router to `__main__.py`
2. ✅ **Fetch Games**: Use `/api/games/{user_id}/fetch`
3. ✅ **Analyze**: Use `/api/analysis/{user_id}/analyze`
4. ✅ **View Results**: Use `/api/analysis/{user_id}/games/{game_id}/analysis`
5. ✅ **Track Progress**: Use `/api/analysis/{user_id}/summary`

**Your Stockfish integration is ready to power chess analysis in IQChess!** 🎉
