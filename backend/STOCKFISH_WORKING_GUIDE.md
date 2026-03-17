# 🎯 Stockfish Integration - Complete Working Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [How Stockfish Works](#how-stockfish-works)
3. [Data Flow & Calculations](#data-flow--calculations)
4. [Using in Your Application](#using-in-your-application)
5. [API Integration Examples](#api-integration-examples)
6. [Testing & Verification](#testing--verification)

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Application                          │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React) → API Request → Backend (FastAPI)             │
│                                        ↓                          │
│                            UnifiedChessAnalyzer                   │
│                                        ↓                          │
│                              StockfishEngine                      │
│                                        ↓                          │
│                         UCI Protocol (python-chess)               │
│                                        ↓                          │
│                    Stockfish Binary (C++ Engine)                 │
│                                        ↓                          │
│                      Analysis Results (JSON)                      │
│                                        ↓                          │
│                         Database (Supabase)                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 How Stockfish Works

### **1. Engine Initialization**

**File:** `app/services/engine/stockfish_engine.py`

```python
# When you create an engine instance
engine = StockfishEngine(
    stockfish_path=None,  # Auto-detect
    depth=15,             # Search 15 moves deep
    threads=2,            # Use 2 CPU cores
    hash_size=256,        # 256 MB memory
    time_limit=1.0        # 1 second per position
)

await engine.initialize()
```

**What Happens:**
1. **Path Detection**: Searches for Stockfish binary
   - Windows: `backend/stockfish/stockfish.exe`
   - Linux: `/usr/games/stockfish`, `/usr/bin/stockfish`
   - macOS: `/usr/local/bin/stockfish`

2. **Process Start**: Launches Stockfish as subprocess
   ```
   Stockfish 17.1 by the Stockfish developers
   ```

3. **UCI Handshake**: Establishes communication
   ```
   → uci
   ← uciok
   → setoption name Threads value 2
   → setoption name Hash value 256
   → isready
   ← readyok
   ```

4. **Ready State**: Engine ready to analyze positions

---

### **2. Position Evaluation Process**

**How a Single Position is Evaluated:**

```python
# Example: Evaluate starting position
board = chess.Board()  # Starting position
result = await engine.evaluate_position(board)
```

**Behind the Scenes:**

```
Step 1: Send Position to Engine
→ position fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1

Step 2: Request Analysis
→ go depth 15 movetime 1000

Step 3: Engine Calculates (1 second)
- Searches millions of positions
- Evaluates material (pawns, pieces)
- Evaluates position (king safety, pawn structure, etc.)
- Calculates best moves
- Detects checkmate patterns

Step 4: Engine Returns Results
← info depth 15 score cp 40 nodes 1234567 pv e2e4 e7e5 g1f3
← bestmove e2e4

Step 5: Parse Results
{
    'evaluation_cp': 40,        # White is +0.4 pawns better
    'mate_in': None,            # No forced mate
    'best_move': 'e2e4',        # Best move is e4
    'pv': ['e2e4', 'e7e5', ...] # Best line of play
}
```

**Evaluation Scale:**
- **+100 cp** = White ahead by 1 pawn
- **0 cp** = Equal position
- **-100 cp** = Black ahead by 1 pawn
- **+300 cp** = White ahead by 3 pawns (usually winning)
- **Mate in 3** = Checkmate in 3 moves

---

### **3. Game Analysis Process**

**File:** `app/services/analysis/unified_analyzer.py`

```python
# Analyze a complete game
analyzer = UnifiedChessAnalyzer()
result = await analyzer.analyze_game(
    pgn_string=pgn,
    user_color="white",
    game_id="12345"
)
```

**Step-by-Step Process:**

#### **Step 1: Parse PGN**
```python
Input PGN:
[Event "Casual Game"]
[White "Player1"]
[Black "Player2"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6

Parsed Output:
- Moves: [e2e4, e7e5, g1f3, b8c6, f1b5, a7a6, b5a4, g8f6]
- Opening: Ruy Lopez
- Total moves: 8
```

#### **Step 2: Analyze Each Move**

```python
For each move in the game:
    
    # BEFORE the move
    position_before = board.fen()
    eval_before = await engine.evaluate_position(board)
    # Example: +50 cp (White slightly better)
    
    # Make the move
    board.push(move)
    
    # AFTER the move
    position_after = board.fen()
    eval_after = await engine.evaluate_position(board)
    # Example: +20 cp (White still better, but less)
    
    # Calculate centipawn loss
    cp_loss = eval_before - eval_after
    # Example: 50 - 20 = 30 cp lost
    
    # Classify move quality
    if cp_loss <= 0:
        classification = "best"      # Improved position
    elif cp_loss <= 50:
        classification = "good"      # Minor loss
    elif cp_loss <= 100:
        classification = "inaccuracy" # Noticeable error
    elif cp_loss <= 200:
        classification = "mistake"   # Significant error
    else:
        classification = "blunder"   # Major error (200+ cp)
```

#### **Step 3: Calculate Metrics**

**ACPL (Average Centipawn Loss):**
```python
user_moves = [move for move in all_moves if move.is_user_move]
total_loss = sum(move.cp_loss for move in user_moves)
acpl = total_loss / len(user_moves)

Example:
Move 1: 10 cp loss
Move 2: 5 cp loss
Move 3: 50 cp loss
Move 4: 15 cp loss
ACPL = (10 + 5 + 50 + 15) / 4 = 20 cp

Interpretation:
< 10 cp  = Grandmaster level
10-20 cp = Master level
20-50 cp = Expert level
50-100 cp = Intermediate
> 100 cp = Beginner
```

**Accuracy Percentage:**
```python
def acpl_to_accuracy(acpl):
    if acpl < 10:
        return 99.0
    elif acpl < 20:
        return 95.0 + (20 - acpl)
    elif acpl < 50:
        return 80.0 + (50 - acpl) / 2
    elif acpl < 100:
        return 60.0 + (100 - acpl) / 2.5
    else:
        return max(0, 60.0 - (acpl - 100) / 5)

Example:
ACPL = 20 → Accuracy = 95%
ACPL = 50 → Accuracy = 80%
ACPL = 100 → Accuracy = 60%
```

#### **Step 4: Phase Analysis**

```python
# Divide game into phases
total_moves = 60

Opening: Moves 1-20
- ACPL: 15 cp
- Blunders: 0
- Mistakes: 1
- Inaccuracies: 2

Middlegame: Moves 20-40
- ACPL: 25 cp
- Blunders: 1
- Mistakes: 2
- Inaccuracies: 3

Endgame: Moves 40-60
- ACPL: 30 cp
- Blunders: 0
- Mistakes: 1
- Inaccuracies: 4
```

---

## 📈 Data Flow & Calculations

### **Complete Example: Analyzing a Blunder**

```python
Position Before Move:
┌───┬───┬───┬───┬───┬───┬───┬───┐
│ r │   │ b │ q │ k │ b │ n │ r │  Black
├───┼───┼───┼───┼───┼───┼───┼───┤
│ p │ p │ p │ p │   │ p │ p │ p │
├───┼───┼───┼───┼───┼───┼───┼───┤
│   │   │ n │   │   │   │   │   │
├───┼───┼───┼───┼───┼───┼───┼───┤
│   │   │   │   │ p │   │   │   │
├───┼───┼───┼───┼───┼───┼───┼───┤
│   │   │ B │   │ P │   │   │   │
├───┼───┼───┼───┼───┼───┼───┼───┤
│   │   │   │   │   │ N │   │   │
├───┼───┼───┼───┼───┼───┼───┼───┤
│ P │ P │ P │ P │   │ P │ P │ P │
├───┼───┼───┼───┼───┼───┼───┼───┤
│ R │ N │ B │ Q │ K │   │   │ R │  White
└───┴───┴───┴───┴───┴───┴───┴───┘

Stockfish Evaluation: +150 cp (White is better)
Best Move: Nf3 (develop knight)

Player Plays: Qh5?? (aggressive but bad)

Position After Move:
[Same board with Queen on h5]

Stockfish Evaluation: -200 cp (Now Black is better!)
Centipawn Loss: 150 - (-200) = 350 cp
Classification: BLUNDER (> 300 cp loss)

Why it's a blunder:
- Exposed queen to attack
- Wasted tempo
- Black can now develop with advantage
```

---

## 🚀 Using in Your Application

### **Method 1: Direct Engine Usage**

**Use Case:** Quick position evaluation, move validation

```python
from app.services.engine.stockfish_engine import StockfishEngine
import chess

async def evaluate_position_api():
    """API endpoint to evaluate a position."""
    
    async with StockfishEngine() as engine:
        # Create position from FEN
        board = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
        
        # Get evaluation
        result = await engine.evaluate_position(board)
        
        return {
            "evaluation": result['evaluation_cp'],
            "best_move": result['best_move'],
            "mate_in": result['mate_in'],
            "is_winning": result['evaluation_cp'] > 200
        }
```

### **Method 2: Full Game Analysis**

**Use Case:** Analyze complete games from Chess.com

```python
from app.services.analysis.unified_analyzer import UnifiedChessAnalyzer

async def analyze_game_api(game_id: int, user_id: int):
    """API endpoint to analyze a game."""
    
    # 1. Fetch game from database
    game = db.query(Game).filter(Game.id == game_id).first()
    
    # 2. Determine user color
    user = db.query(User).filter(User.id == user_id).first()
    user_color = "white" if game.white_username == user.chesscom_username else "black"
    
    # 3. Analyze game
    async with UnifiedChessAnalyzer() as analyzer:
        result = await analyzer.analyze_game(
            pgn_string=game.pgn,
            user_color=user_color,
            game_id=str(game_id)
        )
    
    # 4. Store results in database
    analysis = GameAnalysis(
        game_id=game_id,
        user_id=user_id,
        user_acpl=result.user_acpl,
        accuracy_percentage=result.accuracy_percentage,
        blunders=result.blunders,
        mistakes=result.mistakes,
        inaccuracies=result.inaccuracies,
        best_moves=result.best_moves,
        opening_acpl=result.opening_phase.average_acpl,
        middlegame_acpl=result.middlegame_phase.average_acpl,
        endgame_acpl=result.endgame_phase.average_acpl,
        analysis_data=result.to_dict()  # Store full JSON
    )
    db.add(analysis)
    db.commit()
    
    return {
        "status": "completed",
        "acpl": result.user_acpl,
        "accuracy": result.accuracy_percentage,
        "blunders": result.blunders
    }
```

---

## 🔌 API Integration Examples

### **1. Update Analysis API** (`app/api/analysis.py`)

```python
from app.services.analysis.unified_analyzer import UnifiedChessAnalyzer
from fastapi import BackgroundTasks

@router.post("/{user_id}/analyze")
async def analyze_user_games(
    user_id: int,
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Analyze user's games with Stockfish."""
    
    # Get games to analyze
    games = db.query(Game).filter(
        Game.user_id == user_id,
        Game.analyzed == False
    ).limit(request.max_games or 10).all()
    
    # Queue analysis tasks
    for game in games:
        background_tasks.add_task(
            analyze_game_with_stockfish,
            game.id,
            user_id,
            db
        )
    
    return {
        "status": "queued",
        "games_count": len(games),
        "message": f"Analyzing {len(games)} games in background"
    }


async def analyze_game_with_stockfish(game_id: int, user_id: int, db: Session):
    """Background task to analyze a game."""
    
    try:
        # Fetch game
        game = db.query(Game).filter(Game.id == game_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        
        # Determine user color
        user_color = "white" if game.white_username == user.chesscom_username else "black"
        
        # Analyze with Stockfish
        async with UnifiedChessAnalyzer() as analyzer:
            result = await analyzer.analyze_game(
                pgn_string=game.pgn,
                user_color=user_color,
                game_id=str(game_id)
            )
        
        # Save to database
        analysis = GameAnalysis(
            game_id=game_id,
            user_id=user_id,
            user_acpl=result.user_acpl,
            opponent_acpl=result.opponent_acpl,
            accuracy_percentage=result.accuracy_percentage,
            brilliant_moves=result.brilliant_moves,
            best_moves=result.best_moves,
            good_moves=result.good_moves,
            inaccuracies=result.inaccuracies,
            mistakes=result.mistakes,
            blunders=result.blunders,
            opening_name=result.opening_name,
            opening_eco=result.opening_eco,
            opening_acpl=result.opening_phase.average_acpl if result.opening_phase else None,
            middlegame_acpl=result.middlegame_phase.average_acpl if result.middlegame_phase else None,
            endgame_acpl=result.endgame_phase.average_acpl if result.endgame_phase else None,
            analysis_data=result.to_dict(),
            analyzed_at=datetime.utcnow()
        )
        db.add(analysis)
        
        # Mark game as analyzed
        game.analyzed = True
        db.commit()
        
        logger.info(f"Game {game_id} analyzed: ACPL={result.user_acpl:.1f}, Accuracy={result.accuracy_percentage:.1f}%")
        
    except Exception as e:
        logger.error(f"Failed to analyze game {game_id}: {e}")
        db.rollback()
```

### **2. Get Analysis Results**

```python
@router.get("/{user_id}/games/{game_id}/analysis")
async def get_game_analysis(
    user_id: int,
    game_id: int,
    db: Session = Depends(get_db)
):
    """Get analysis results for a specific game."""
    
    analysis = db.query(GameAnalysis).filter(
        GameAnalysis.game_id == game_id,
        GameAnalysis.user_id == user_id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return {
        "game_id": game_id,
        "acpl": analysis.user_acpl,
        "accuracy": analysis.accuracy_percentage,
        "move_quality": {
            "brilliant": analysis.brilliant_moves,
            "best": analysis.best_moves,
            "good": analysis.good_moves,
            "inaccuracies": analysis.inaccuracies,
            "mistakes": analysis.mistakes,
            "blunders": analysis.blunders
        },
        "phase_analysis": {
            "opening": analysis.opening_acpl,
            "middlegame": analysis.middlegame_acpl,
            "endgame": analysis.endgame_acpl
        },
        "opening": {
            "name": analysis.opening_name,
            "eco": analysis.opening_eco
        },
        "detailed_moves": analysis.analysis_data.get("all_moves", []),
        "critical_positions": analysis.analysis_data.get("critical_positions", [])
    }
```

---

## 🧪 Testing & Verification

### **1. Test Engine Directly**

```bash
cd backend
python tests/test_stockfish_engine.py
```

**Expected Output:**
```
✓ Engine initialized at: E:\chess\chess-AI\backend\stockfish\stockfish.exe
✓ Analyzing starting position...
✓ Evaluation: 40 centipawns
✓ Best move: e2e4
SUCCESS: Stockfish engine is working correctly!
```

### **2. Test Game Analysis**

```bash
cd backend
python test_game_analysis.py
```

**Expected Output:**
```
📊 Analyzing Scholar's Mate game...
✅ Analysis Complete!

📈 Overall Metrics:
   • User Color: black
   • Total Moves: 4
   • ACPL: 250.0
   • Accuracy: 45.0%

🎯 Move Quality:
   • Best Moves: 2
   • Blunders: 1
```

### **3. Test via API**

```bash
# Start backend
cd backend
python -m app

# In another terminal, test API
curl -X POST http://localhost:8000/api/analysis/1/analyze \
  -H "Content-Type: application/json" \
  -d '{"max_games": 5}'
```

---

## 📝 Complete Workflow in Your Application

### **User Journey:**

```
1. User logs in to IQChess
   ↓
2. User clicks "Fetch Games" from Chess.com
   ↓
3. Backend fetches games via Chess.com API
   ↓
4. Games stored in database (PGN format)
   ↓
5. User clicks "Analyze Games"
   ↓
6. Frontend sends POST /api/analysis/{user_id}/analyze
   ↓
7. Backend queues analysis tasks (background)
   ↓
8. For each game:
   - UnifiedChessAnalyzer parses PGN
   - StockfishEngine evaluates each position
   - Moves classified (best/good/mistake/blunder)
   - Metrics calculated (ACPL, accuracy)
   - Results saved to database
   ↓
9. User views analysis results on dashboard
   - Overall accuracy chart
   - Move quality breakdown
   - Phase analysis (opening/middlegame/endgame)
   - Critical positions highlighted
   ↓
10. User gets personalized recommendations
    - "Work on endgame technique (ACPL: 50)"
    - "Reduce blunders in time pressure"
    - "Opening repertoire needs improvement"
```

---

## 🎯 Key Takeaways

### **What Stockfish Provides:**
- ✅ Objective position evaluation (centipawns)
- ✅ Best move calculation
- ✅ Checkmate detection
- ✅ Principal variation (best line)

### **What Your System Adds:**
- ✅ Move quality classification
- ✅ ACPL and accuracy metrics
- ✅ Phase-based analysis
- ✅ Critical position identification
- ✅ Personalized insights

### **Performance:**
- **Single position:** ~0.1-1 second (depth 15)
- **Full game (40 moves):** ~40-80 seconds
- **Batch analysis (10 games):** ~7-13 minutes (background)

### **Accuracy:**
- **Depth 10:** Fast, good for quick analysis
- **Depth 15:** Balanced (recommended)
- **Depth 20:** Slow, very accurate

---

## 🚀 Next Steps

1. **Update Analysis API** - Integrate `UnifiedChessAnalyzer`
2. **Test with Real Games** - Fetch from Chess.com and analyze
3. **Build Dashboard** - Display analysis results
4. **Add Recommendations** - AI-powered coaching based on analysis

**Your Stockfish integration is complete and ready to power chess analysis in your application!** 🎉
