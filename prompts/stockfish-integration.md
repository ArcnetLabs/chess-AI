# Prompt: Stockfish Integration

Use when adding new analysis features, changing how positions are evaluated, or extending the Stockfish engine pool.

---

## Critical Rule (read before proceeding)

**All Stockfish access goes through `backend/app/services/engine/engine_pool.py`.**

No exceptions. No `chess.engine.SimpleEngine.popen_uci()` in routes, tasks, or other services. If you find this pattern anywhere other than `engine_pool.py`, it is a bug — fix it before adding more code.

```bash
# Verify before starting:
rg "SimpleEngine\|popen_uci\|chess\.engine\." backend/app/ --type py
# Expected: results only inside engine_pool.py
```

---

## Template

```
We are adding Stockfish-based analysis to ChessIQ.

Feature: <describe what analysis is needed — e.g. "endgame position scoring", "opening deviation detection">

STEP 1 — Inspect the existing analysis pipeline:
1. Read the engine pool API:
   rg "def analyze\|def batch_analyze\|async def" backend/app/services/engine/ --type py
2. Read the unified analyzer to understand current analysis flow:
   backend/app/services/analysis/unified_analyzer.py (read the full file)
3. Read the evaluation thresholds:
   rg "BLUNDER\|MISTAKE\|INACCURACY\|cp_delta\|threshold" backend/app/ --type py
4. Report: can the existing pipeline cover this feature? If yes, extend it. If no, explain why.

STEP 2 — Inspect the reference source if extending engine pool behaviour:
rg "class.*Engine\|async def analyze\|AnalysisResult\|InfoDict" reference/stockfish/python-chess/chess/engine.py
Confirm the exact method signature and result structure before implementing.

STEP 3 — Implement using the correct pattern:
For new analysis types (extend unified_analyzer.py):
  Add a method to UnifiedAnalyzer. Never create UnifiedAnalyzer2 or a parallel analyzer class.

For new engine pool behaviour (extend engine_pool.py):
  Add a method to the pool class. Document the depth and time_limit used.

For new Celery task (extend analysis_tasks.py):
  Add a function to the existing file. Never create a new task file for analysis work.

Depth guide (from reference/stockfish/README.md):
  Quick hint:     depth=12, time_limit=0.5
  Full analysis:  depth=18, time_limit=1.0
  Move rec:       depth=15, time_limit=1.0
  Critical pos:   depth=20, time_limit=2.0

STEP 4 — Verify the implementation:
Run: python -m mypy app/ --ignore-missing-imports
Verify no new Stockfish access outside pool:
  rg "SimpleEngine\|popen_uci\|chess\.engine\." backend/app/ --type py
  (should only appear in engine_pool.py)
Verify no hardcoded thresholds:
  rg "depth=\d+" backend/app/api/ backend/app/tasks/ --type py
  (should return 0)

STEP 5 — Summary:
State: which reference files confirmed the engine API, whether UnifiedAnalyzer was extended
or a new service method was created (with justification), and the depth/time settings used.

Files to touch:
<list specific files>

Do not touch:
backend/app/api/ (unless adding the route endpoint)
backend/app/tasks/ (unless adding a new async task entry point)
```

---

## What Stockfish Provides vs. What It Does Not

| Stockfish provides (authoritative) | Never ask Stockfish to |
|------------------------------------|----------------------|
| Best move (bestmove UCI) | Explain why a move is good (LLM does that) |
| Centipawn score (cp) | Identify the opening (use PGN ECO header) |
| Depth-verified evaluation | Make coaching decisions (RecommendationEngine does that) |
| Alternative lines (multipv) | Format output for users (routes/services do that) |

---

## Engine Pool Extension Pattern

```python
# In backend/app/services/engine/engine_pool.py

async def analyze_endgame(
    self, board: chess.Board, depth: int = 20
) -> EndgameAnalysis:
    """
    Specialized endgame analysis at higher depth.
    Only use when the position has <= 7 pieces (tablebase territory).
    """
    if chess.popcount(board.occupied) > 7:
        raise ValueError("analyze_endgame requires <= 7 pieces")
    engine = await self._acquire()
    try:
        result = await engine.analyse(board, chess.engine.Limit(depth=depth))
        return EndgameAnalysis.from_info(result)
    finally:
        await self._release(engine)
```

## Common Mistakes to Prevent

```bash
# This is wrong — never do this outside engine_pool.py:
engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
result = engine.analyse(board, chess.engine.Limit(depth=15))
engine.quit()

# This is wrong — never hardcode in a route:
@router.post("/analyze")
async def analyze():
    pool = get_engine_pool()
    result = await pool.analyze(board, depth=18)  # ← depth belongs in service layer, not here
```
