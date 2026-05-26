# Skill: Refactor Loop

**When to use:** After the grep review phase returns findings, after a size check flags oversized files, after a sprint of heavy AI code generation, or whenever duplicated logic is confirmed. This skill drives iterative convergence — keep looping until the codebase reaches a clean state.

This skill is distinct from `skills/review-loop.md` (which handles PR feedback cycles) and `skills/code-cleanup.md` (which is a post-feature sweep). The refactor loop is for **structural improvement** — extracting services, splitting files, consolidating duplicated logic.

---

## The Convergence Loop

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   IDENTIFY TARGET                                   │
│        │                                            │
│        ▼                                            │
│   READ FULL CONTEXT  ──► check reference/           │
│        │                                            │
│        ▼                                            │
│   MAKE ONE CHANGE  (split / extract / consolidate)  │
│        │                                            │
│        ▼                                            │
│   RUN GREP CHECK  ──► PASS? ──► COMMIT              │
│        │                  │                         │
│       FAIL                └──► NEXT TARGET          │
│        │                                            │
│        ▼                                            │
│   FIX, RE-RUN  (back to top)                        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Critical rule:** One refactor target per commit. Never change the external behaviour — only structure.

---

## Convergence Conditions

Stop the loop when ALL of the following are true:

- [ ] `.\scripts\review-loops\full-review.ps1` exits 0
- [ ] No Python service file exceeds 300 lines
- [ ] No React component exceeds 200 lines
- [ ] No Next.js page exceeds 150 lines
- [ ] All new files have tests or are delegating work to tested services
- [ ] All `TODO: refactor` and `FIXME` comments have been addressed or filed as issues

---

## Refactor Playbooks

### Playbook 1: Split an oversized service file

**Trigger:** `check-file-sizes.ps1` reports `backend/app/services/chess_service.py` > 300 lines.

```bash
# Step 1: Map responsibilities
rg "^def " backend/app/services/chess_service.py --type py
# List every function — group by: parsing / analysis / fetching / utility

# Step 2: Identify the extraction candidate (highest cohesion group)
# Example: all PGN functions group together → extract to pgn_parser.py

# Step 3: Create new file
# New file: backend/app/services/pgn_parser.py
# Move: parse_pgn(), validate_pgn(), pgn_to_fen()

# Step 4: Update imports
rg "from app.services.chess_service import" backend/ --type py
# Update each import site to import from the new module

# Step 5: Run grep checks
.\scripts\review-loops\check-stockfish-violations.ps1
.\scripts\review-loops\check-route-violations.ps1
.\scripts\review-loops\check-duplicates.ps1

# Step 6: Run tests
cd backend && pytest tests/ -x -q -k "pgn or chess"
```

### Playbook 2: Extract a React component

**Trigger:** `check-file-sizes.ps1` reports `frontend/src/components/ChessBoard.tsx` > 200 lines.

```bash
# Step 1: Map rendering sections
# Scan for distinct rendering groups: board squares, piece overlays, move highlights, controls

# Step 2: Identify the extraction candidate
# Largest self-contained section → extract to its own component file

# Step 3: Extract
# New: frontend/src/components/chess/BoardSquare.tsx
# Move: renderSquare() function → becomes default export of BoardSquare.tsx

# Step 4: Import and replace in parent
# ChessBoard.tsx: import BoardSquare from './chess/BoardSquare'
# Replace inline renderSquare call with <BoardSquare ... />

# Step 5: Check component sizes
.\scripts\review-loops\check-file-sizes.ps1

# Step 6: Smoke test
cd frontend && npm test -- --testPathPattern=ChessBoard --watchAll=false
```

### Playbook 3: Extract a custom hook

**Trigger:** A page or component contains more than 3 `useState`/`useEffect` calls, or has data-fetching logic.

```bash
# Step 1: Identify the state group
rg "useState|useEffect|useCallback|useMemo" frontend/src/pages/dashboard.tsx

# Step 2: Group by concern
# Example: gameId, gameData, isLoading, fetchGame → belongs in useGame.ts

# Step 3: Create hook
# New: frontend/src/hooks/useGame.ts
# Extract: state declarations + fetch logic + return { gameData, isLoading, error }

# Step 4: Simplify the page
# Page becomes: const { gameData, isLoading } = useGame(gameId)
# Page renders data — no fetch logic remaining

# Step 5: Verify size
.\scripts\review-loops\check-file-sizes.ps1
```

### Playbook 4: Consolidate duplicate service logic

**Trigger:** `check-duplicates.ps1` finds the same function defined in two files.

```bash
# Step 1: Identify both definitions
rg "def fetch_game" backend/app/ --type py

# Step 2: Compare them
# Read both files and understand which is more complete / correct

# Step 3: Pick the canonical location
# Winner: backend/app/services/chesscom_api.py (the correct service layer)
# Loser: backend/app/api/games.py (inline in a route — wrong layer)

# Step 4: Remove the duplicate
# Delete the function from games.py
# Import from the service in games.py:
#   from app.services.chesscom_api import fetch_game

# Step 5: Verify no other callers
rg "def fetch_game\|from.*import.*fetch_game" backend/ --type py

# Step 6: Run full suite
.\scripts\review-loops\full-review.ps1
```

### Playbook 5: Consolidate duplicated Stockfish logic

**Trigger:** `check-stockfish-violations.ps1` finds `popen_uci` / `StockfishEngine(` outside the engine pool, or `check-duplicates.ps1` finds multiple engine depth constants.

```bash
# Step 1: Locate all Stockfish call sites
rg "SimpleEngine|popen_uci|depth=" backend/ --type py

# Step 2: Identify which should be the canonical engine pool
# It must be: backend/app/services/engine_pool.py

# Step 3: Remove direct calls from routes/tasks
# Replace with: pool = get_engine_pool(); result = await pool.analyze(board, depth=ANALYSIS_DEPTH)

# Step 4: Consolidate depth constants
rg "depth=\d+" backend/ --type py
# Replace all with: from app.core.config import ANALYSIS_DEPTH

# Step 5: Add grep-exempt to engine_pool.py itself
# engine = chess.engine.SimpleEngine.popen_uci(path)  # grep-exempt: engine pool definition

# Step 6: Verify
.\scripts\review-loops\check-stockfish-violations.ps1
```

---

## Anti-Patterns to Avoid During Refactoring

| Anti-pattern | Why it's harmful | Correct approach |
|-------------|----------------|-----------------|
| Changing behaviour while refactoring | Tests break and you can't tell if it's the refactor or the bug | Split into: refactor commit (no behaviour change) + fix commit |
| Mega-refactor PR (50+ files) | Impossible to review, high risk of merge conflicts | Extract one file per PR — merge incrementally |
| Deleting "redundant" code without tracing all callers | Breaks runtime even if tests pass | `rg "function_name"` before deleting — check every call site |
| Extracting to a new abstraction that's used only once | Premature abstraction — adds indirection for no benefit | Only extract when there are ≥ 2 callers or the file exceeds the size limit |
| Renaming during extraction | Double the diff — hard to review | Rename in a separate commit after extraction is proven clean |

---

## Commit Protocol During Refactoring

Each refactor step gets its own commit with a structured message:

```
refactor: extract pgn_parser from chess_service

- Move parse_pgn(), validate_pgn(), pgn_to_fen() to pgn_parser.py
- Update 3 import sites
- No behaviour change — all existing tests pass

Resolves: check-file-sizes.ps1 FS-1 finding (chess_service.py was 387 lines)
```

---

## Loop Exit Checklist

Before declaring the refactor loop complete:

```powershell
# Run the full suite — must exit 0
.\scripts\review-loops\full-review.ps1

# Confirm no regressions
cd backend && pytest tests/ -x -q
cd ..\frontend && npm test -- --watchAll=false

# Check git log — confirm all refactor commits are atomic
git log --oneline -10
```

When all checks pass and tests are green: the loop is done. Open the PR.
