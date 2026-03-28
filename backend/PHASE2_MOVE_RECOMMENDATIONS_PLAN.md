# Phase 2: Move Recommendation System - Implementation Plan

**Goal:** Real-time position analysis with Stockfish-powered move suggestions and explanations

---

## Architecture Overview

```
User Position (FEN) → API Endpoint → Move Recommendation Service
                                            ↓
                                      Stockfish Engine
                                            ↓
                                    Analyze Position
                                            ↓
                        ┌───────────────────┴───────────────────┐
                        ↓                                       ↓
                  Best Moves (3-5)                      Position Evaluation
                        ↓                                       ↓
                  Move Explanations                    Tactical Themes
                        ↓                                       ↓
                    Response JSON ←─────────────────────────────┘
```

---

## Components to Build

### 1. Stockfish Service Enhancement
**File:** `backend/app/services/analysis/stockfish_service.py`

**Features:**
- Position analysis with multiple candidate moves
- Move evaluation and comparison
- Tactical pattern detection
- Best move calculation with variations

### 2. Move Recommendation Service
**File:** `backend/app/services/moves/move_recommender.py`

**Features:**
- Analyze current position
- Generate top 3-5 move candidates
- Explain why each move is good/bad
- Detect tactical themes (pins, forks, skewers, etc.)
- Provide learning insights

### 3. Move Explanation Generator
**File:** `backend/app/services/moves/move_explainer.py`

**Features:**
- Natural language explanations for moves
- Tactical pattern descriptions
- Strategic concept explanations
- Beginner-friendly language

### 4. API Endpoints
**File:** `backend/app/api/moves.py`

**Endpoints:**
- `POST /api/moves/analyze` - Analyze position and get move recommendations
- `POST /api/moves/compare` - Compare two moves
- `GET /api/moves/best/{fen}` - Get best move for position
- `POST /api/moves/explain` - Get detailed explanation for a move

### 5. Data Models
**File:** `backend/app/models/moves.py`

**Models:**
- `MoveRecommendation` - Store move analysis results
- `PositionAnalysis` - Store position evaluations
- `TacticalTheme` - Store detected tactical patterns

---

## Implementation Steps

### Step 1: Enhance Stockfish Service ✓
- Add multi-PV (principal variation) analysis
- Implement move comparison
- Add tactical pattern detection
- Calculate position evaluation

### Step 2: Create Move Recommendation Service
- Build move candidate generator
- Implement move scoring
- Add explanation generation
- Integrate with Stockfish

### Step 3: Build Move Explainer
- Create explanation templates
- Implement tactical theme detector
- Add strategic concept mapper
- Generate natural language output

### Step 4: Add API Endpoints
- Create move analysis endpoint
- Add move comparison endpoint
- Implement best move endpoint
- Add explanation endpoint

### Step 5: Database Schema (Optional)
- Add tables for storing move analyses
- Cache position evaluations
- Store user move history

### Step 6: Testing
- Unit tests for Stockfish integration
- Integration tests for move service
- API endpoint tests
- Manual testing with real positions

---

## Data Structures

### MoveRecommendation
```python
{
    "move": "Nf3",
    "uci": "g1f3",
    "evaluation": 0.5,
    "rank": 1,
    "explanation": "Develops the knight to a central square...",
    "tactical_themes": ["development", "center_control"],
    "variations": ["1. Nf3 d5 2. d4 Nf6"],
    "pros": ["Controls center", "Develops piece"],
    "cons": ["Blocks f-pawn"],
    "difficulty": "beginner"
}
```

### PositionAnalysis
```python
{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "evaluation": 0.0,
    "best_move": "e2e4",
    "candidate_moves": [...],
    "tactical_themes": ["open_game", "king_safety"],
    "phase": "opening",
    "material_balance": 0,
    "piece_activity": {...}
}
```

---

## API Examples

### Analyze Position
```bash
POST /api/moves/analyze
{
    "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "depth": 15,
    "num_moves": 5
}

Response:
{
    "position": {
        "fen": "...",
        "evaluation": 0.3,
        "phase": "opening"
    },
    "recommendations": [
        {
            "move": "Bb5",
            "evaluation": 0.5,
            "explanation": "Develops bishop and pins the knight...",
            "tactical_themes": ["pin", "development"]
        },
        ...
    ],
    "insights": "White has a slight advantage due to better development."
}
```

### Compare Moves
```bash
POST /api/moves/compare
{
    "fen": "...",
    "moves": ["Nf3", "Nc3"]
}

Response:
{
    "comparison": [
        {
            "move": "Nf3",
            "evaluation": 0.5,
            "better_because": "Controls more central squares"
        },
        {
            "move": "Nc3",
            "evaluation": 0.2,
            "worse_because": "Blocks c-pawn, less flexible"
        }
    ],
    "recommendation": "Nf3 is better by 0.3 pawns"
}
```

---

## Tactical Themes to Detect

1. **Pins** - Piece pinned to king/queen
2. **Forks** - One piece attacks multiple pieces
3. **Skewers** - Forcing valuable piece to move, exposing less valuable piece
4. **Discovered Attacks** - Moving one piece reveals attack from another
5. **Double Attacks** - Attacking two pieces simultaneously
6. **Sacrifices** - Giving up material for advantage
7. **Checkmate Patterns** - Back rank mate, smothered mate, etc.
8. **Pawn Breaks** - Strategic pawn advances
9. **Piece Coordination** - Multiple pieces working together
10. **King Safety** - Castling, pawn shield, etc.

---

## Success Criteria

- ✅ Stockfish integration returns top 5 moves with evaluations
- ✅ Move explanations are clear and educational
- ✅ Tactical themes are accurately detected
- ✅ API response time < 2 seconds
- ✅ Explanations suitable for beginners
- ✅ All endpoints tested and working

---

## Timeline

**Estimated Time:** 4-6 hours

- **Step 1:** Stockfish service (1 hour)
- **Step 2:** Move recommender (1.5 hours)
- **Step 3:** Move explainer (1 hour)
- **Step 4:** API endpoints (1 hour)
- **Step 5:** Testing (0.5 hour)

---

## Dependencies

- ✅ Stockfish binary (already configured)
- ✅ python-chess library (already installed)
- ✅ FastAPI (already installed)
- ✅ PostgreSQL (already running)

---

**Ready to implement!** Starting with Stockfish service enhancement.
