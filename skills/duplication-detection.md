# Skill: Duplication Detection

**When to use:** Before introducing a new service, utility, hook, or helper function — and after any AI-generated code dump. This skill goes beyond the B-series grep checks to systematically detect duplication at multiple levels: exact copies, structural clones, and semantic equivalents.

The B-series in `scripts/review-loops/check-duplicates.ps1` catches known duplication patterns. This skill catches **unknown and emergent** duplication.

---

## Levels of Duplication

| Level | Description | Detection method |
|-------|-------------|-----------------|
| **L1 — Exact copy** | Identical function/block pasted into two files | `rg` for function names, bodies |
| **L2 — Structural clone** | Same algorithm, different variable names | Pattern-based grep |
| **L3 — Semantic equivalent** | Different code, same business intent | Manual analysis after L1/L2 |
| **L4 — Emergent** | Two services that solve the same problem divergently | Architecture review (see `skills/architecture-review.md`) |

This skill covers L1 and L2. L3 and L4 require human or Opus-level reasoning.

---

## Phase 1: Before Writing New Code (Pre-Implementation Check)

Run this before creating any new function, service, or hook.

```bash
# Replace <concept> with your domain (e.g. "game", "analysis", "move", "pgn")
$concept = "analysis"

echo "=== Backend: functions matching $concept ==="
rg "def.*$concept" backend/app/ --type py

echo "=== Frontend: functions/hooks matching $concept ==="
rg "(function|const|export).*$concept" frontend/src/ --type ts
rg "(function|const|export).*$concept" frontend/src/ --type tsx

echo "=== Services: does a $concept service already exist? ==="
Get-ChildItem backend/app/services/ -Filter "*$concept*"
Get-ChildItem frontend/src/hooks/ -Filter "*$concept*"
```

**Decision tree:**

```
Found existing function? ──YES──► Use it. Do not create a new one.
         │
        NO
         │
         ▼
Found existing service file? ──YES──► Add method to existing file.
         │
        NO
         │
         ▼
    Create new file.
```

---

## Phase 2: Scanning for Exact Function Duplicates (L1)

### Backend

```bash
# Find all function definitions
rg "^def [a-z_]+" backend/app/ --type py -o --no-filename | sort | uniq -d
# Duplicated names printed here — each one is a candidate for consolidation

# For each duplicate name, find its locations
rg "^def fetch_game" backend/app/ --type py
```

Common backend duplication patterns to check explicitly:

```bash
# Game-related
rg "def (fetch|get|load)_(game|games|pgn)" backend/app/ --type py

# Analysis-related
rg "def (analyze|evaluate|assess)_(position|move|game|board)" backend/app/ --type py

# User-related
rg "def (get|fetch|load)_(user|current_user|profile)" backend/app/ --type py

# Engine/Stockfish
rg "def (run|get|create|init)_(engine|stockfish|analysis)" backend/app/ --type py

# Database helpers
rg "def (get|create|update|delete)_(db|session|connection)" backend/app/ --type py
```

### Frontend

```bash
# Find duplicate hook names
rg "export (function|const) use[A-Z]" frontend/src/ --type ts -o --no-filename | sort | uniq -d

# Explicit hook duplicate checks
rg "export (function|const) use(Game|Chess|Analysis|Move|User|Auth)" frontend/src/ --type ts

# Duplicate API call functions
rg "export (async function|const) (fetch|get|post|update|delete)[A-Z]" frontend/src/lib/ --type ts

# Duplicate utility functions
rg "export function (format|parse|validate|convert)" frontend/src/ --type ts | sort
```

---

## Phase 3: Structural Clone Detection (L2)

Structural clones share the same shape even when names differ. Look for recurring patterns.

### Repeated request/response wrapper pattern

```bash
# Multiple try/except blocks with identical error handling (should use a shared helper)
rg "try:.*except.*HTTPException" backend/app/api/ --type py -l
# > 3 files = candidate for a shared error handler decorator

# Multiple identical response model shapes
rg "class.*Response.*BaseModel" backend/app/schemas/ --type py
# Read the fields — look for User/Player/Profile responses that are structurally identical
```

### Repeated React data-fetching pattern

```bash
# Multiple useEffect + useState patterns that follow the same shape
rg "const \[.*loading.*\] = useState|const \[.*data.*\] = useState" frontend/src/pages/ --type tsx
# Each page with 2+ useState for loading/data/error is a structural clone → extract to useQuery hook

# Multiple manual fetch patterns (should all use React Query)
rg "useEffect.*\[\], fetch\|useEffect.*\[\], axios" frontend/src/ --type tsx
```

### Repeated validation patterns

```bash
# Multiple similar Pydantic validators (should use shared base models)
rg "class.*BaseModel" backend/app/schemas/ --type py
# Look for UserCreate, UserUpdate, UserResponse that share 80% of fields
# → consolidate to UserBase + specific extension models

# Multiple similar TypeScript validation functions
rg "const validate[A-Z]" frontend/src/ --type ts
```

---

## Phase 4: Import Duplication Detection

Repeated imports reveal missing barrel files or over-fragmented utilities.

```bash
# Find the most frequently imported modules (top candidates for consolidation)
rg "^from app\." backend/app/api/ --type py -o --no-filename | sort | uniq -c | sort -rn | head -10

# Types that are re-imported in every file (should be in a shared types barrel)
rg "^import.*from.*types/" frontend/src/ --type tsx | grep -o "from.*'" | sort | uniq -c | sort -rn | head -10

# Supabase client imported outside the lib layer
rg "from @supabase" frontend/src/ --type ts --type tsx | rg -v "lib/supabase/"
```

---

## Phase 5: Duplication Report

After running Phases 1–4, produce:

```markdown
## Duplication Detection Report — <date>

### L1 — Exact Duplicates Found

| Function | Location 1 | Location 2 | Action |
|----------|-----------|-----------|--------|
| `fetch_game()` | `api/games.py:34` | `services/chesscom_api.py:12` | Delete `api/games.py` version, import from service |
| `useGameData()` | `pages/dashboard.tsx` | `hooks/useGame.ts` | Delete page version, use hook |

### L2 — Structural Clones Found

| Pattern | Files | Action |
|---------|-------|--------|
| Manual loading state pattern | 4 page files | Extract to `useAsyncData` hook |
| UserCreate/UserUpdate schemas | schemas/users.py | Consolidate to `UserBase` |

### L3 — Semantic Equivalents (requires review)

| Description | Files | Note |
|-------------|-------|------|
| Two "position evaluation" concepts | `analysis_service.py`, `coach_service.py` | Different contexts — may be intentional |

### Consolidation Priority

1. `fetch_game()` duplicate — HIGH (breaks service layer rule)
2. Manual loading state in 4 pages — MEDIUM (maintenance burden)
3. Schema consolidation — LOW (cosmetic)

### Pre-Implementation Clearance

All checks run. No existing implementation found for `[new feature]`. Safe to create new file.
```

---

## Duplication Tolerance Policy

Not all duplication is wrong. Apply judgment:

| Situation | Tolerate? | Reason |
|-----------|-----------|--------|
| `engine_pool.py` creates an engine instance | Yes | It IS the engine factory |
| `test_*.py` duplicates some setup | Yes | Test isolation is intentional |
| `auth/callback.tsx` has inline auth logic | Yes | Edge case with no reuse |
| `api/games.py` re-implements `fetch_game` | **No** | Pure duplication with no justification |
| Two components with similar structure | Depends | If they diverge over time, separation is correct |

When tolerating duplication, always add a comment:

```python
# duplication-ok: this is the engine pool itself — not a consumer of engine_pool.py
engine = chess.engine.SimpleEngine.popen_uci(path)
```

---

## Running This Skill

### Quick pre-implementation check (30 seconds)

```bash
$concept = "YOUR_CONCEPT_HERE"
rg "def.*$concept" backend/app/ --type py
rg "use$concept|fetch$concept" frontend/src/ --type ts
```

### Full duplication audit (5–10 minutes)

Run all four phases above and produce the Duplication Report.

### Automated baseline (via scripts)

```powershell
# Runs the B-series automated checks from check-duplicates.ps1
.\scripts\review-loops\check-duplicates.ps1
```

The automated B-series checks known duplication patterns. This skill handles discovery of unknown duplication that hasn't been encoded into a check yet.
