# Skill: Chess Analysis Workflow

**When to use:** When implementing or modifying any feature that involves chess game analysis, position evaluation, pattern recognition, or move recommendations.

---

## ChessIQ Analysis Pipeline (current implementation)

```
User requests analysis
  ↓
GET /api/v1/users/{username}/games  (chesscom_api.py fetches from Chess.com)
  ↓
analyze_games_task.delay(user_id)   (Celery task queued)
  ↓
UnifiedAnalyzer.analyze_game(pgn)   (app/services/analysis/unified_analyzer.py)
  ↓
  ├── EnginePool.analyze(board)     (app/services/engine/engine_pool.py → Stockfish)
  ├── MoveRecommender               (app/services/moves/move_recommender.py)
  └── RecommendationEngine          (app/services/coaching/recommendation_engine.py)
  ↓
Results stored in DB (game analysis + insights)
  ↓
GET /api/v1/users/{id}/insights     (aggregated coaching insights)
  ↓
ChessCoach.generate_response(context) (LLM response with Stockfish-grounded context)
```

---

## Stockfish Integration Rules

### Engine Pool Usage

```python
from app.services.engine.engine_pool import get_engine_pool

# Always use the pool — never instantiate engines directly
pool = get_engine_pool()

# Analyze a single position
result = await pool.analyze(board=board, depth=15, time_limit=1.0)

# Batch analysis (preferred for full-game analysis)
results = await pool.batch_analyze(positions=[(board, depth) for board in boards])
```

### Analysis Depth Guide

| Use case | Depth | Time limit | Reason |
|----------|-------|-----------|--------|
| Quick move hint | 12 | 0.5s | Low latency for real-time |
| Full game analysis | 18 | 1.0s/pos | Accuracy for insights |
| Move recommendation | 15 | 1.0s | Balance speed vs quality |
| Critical position | 20 | 2.0s | Opening/endgame precision |

### What Stockfish Provides vs. What the LLM Provides

```
Stockfish (authoritative):       LLM (translation layer):
  ✓ Best moves                     ✓ Natural language explanation
  ✓ Position evaluation (CP)       ✓ Pattern naming and coaching tone
  ✓ Blunder/mistake classification ✓ Improvement advice
  ✓ Opening identification         ✓ Conversational response
  ✗ Explanation                    ✗ Chess truth (LLM is NOT a chess engine)
```

**The LLM never overrides Stockfish data. It translates it.**

---

## Pattern Recognition Workflow

The `RecommendationEngine` identifies recurring mistakes across a user's games:

```python
# Recognized pattern categories (RecommendationEngine)
PATTERN_CATEGORIES = [
    "tactical_blindness",      # Missing forks, pins, skewers
    "endgame_technique",       # King activation, pawn promotion
    "time_pressure_collapse",  # Blunders in time trouble
    "opening_preparation",     # Deviating from book early
    "positional_weaknesses",   # Weak square complexes, isolated pawns
]
```

When adding new pattern types:
1. Add to the category list in `recommendation_engine.py`.
2. Define the detection heuristic (CP loss threshold, position feature).
3. Add a test case in `backend/tests/test_recommendation_engine.py`.

---

## LLM Context Assembly

The `ChessCoach` assembles context for the LLM from Stockfish-grounded data:

```python
# Context budget (approximate token costs)
system_prompt:      ~300 tokens
game_summary:       ~200 tokens per game (max 5 games)
pattern_context:    ~150 tokens per pattern (max 3 patterns)
conversation_history: ~100 tokens per message (max 10 turns)
user_question:      varies
─────────────────────────────────────────
Total target:       < 4000 tokens for local models, < 8000 for hosted
```

**Hallucination prevention:**
- Only include moves that Stockfish actually evaluated (CP scores present).
- Never ask the LLM to "recommend the best move" — Stockfish does that.
- LLM prompt always includes: "Base all advice on the Stockfish analysis provided. Do not suggest moves not in the analysis."

---

## Adding a New Analysis Feature

1. **Check existing analyzers** — is this an extension of `UnifiedAnalyzer` or a new service?
2. **Define the Stockfish query** — what position/depth/lines are needed?
3. **Define the DB schema** — where does the result get stored? (new table or existing `game_analyses`?)
4. **Define the Celery task** — is this sync (< 1s) or async (background)?
5. **Define the API contract** — what does the frontend/LLM receive?
6. **Add tests** in `backend/tests/test_analysis_engine_core.py`.

---

## Verification Checklist

- [ ] No raw Stockfish subprocess calls — only via `engine_pool.py`.
- [ ] LLM responses grounded in Stockfish output (CP scores, best moves present in context).
- [ ] Analysis results stored with `user_id` foreign key (never anonymous).
- [ ] Engine pool properly released in error paths.
- [ ] New patterns have test cases.
