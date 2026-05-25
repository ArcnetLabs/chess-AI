# Skill: Architecture Review

**When to use:** Monthly health audits, post-major-feature, after a long sprint of AI-generated code, or whenever the codebase "feels" like it's drifting from its design.

This skill goes beyond the pre-merge grep checks. It produces a complete architectural health report covering structural drift, dependency hygiene, service boundary integrity, and technical debt accumulation.

---

## When Architecture Review Differs from Grep-Loop Review

| Grep-Loop Review (`skills/grep-loop-review.md`) | Architecture Review (this skill) |
|--------------------------------------------------|----------------------------------|
| Pre-merge gate — catches single violations | Periodic audit — finds systemic drift |
| Runs in ~10 seconds | Takes 20–40 minutes |
| Binary: pass/fail | Produces a scored health report |
| Looks at changed files | Looks at the entire codebase |
| Fixes before merging | Informs sprint planning |

---

## Step 1: Structural Inventory

Map the current state before judging it.

```bash
# Count files per layer — growth imbalances reveal missing abstractions
echo "=== Backend file counts ==="
(Get-ChildItem backend/app/api/ -Filter *.py -Recurse).Count
(Get-ChildItem backend/app/services/ -Filter *.py -Recurse).Count
(Get-ChildItem backend/app/tasks/ -Filter *.py -Recurse).Count
(Get-ChildItem backend/app/models/ -Filter *.py -Recurse).Count

echo "=== Frontend file counts ==="
(Get-ChildItem frontend/src/components/ -Filter *.tsx -Recurse).Count
(Get-ChildItem frontend/src/pages/ -Filter *.tsx -Recurse).Count
(Get-ChildItem frontend/src/hooks/ -Filter *.ts -Recurse).Count
(Get-ChildItem frontend/src/lib/ -Filter *.ts -Recurse).Count

# Largest files (highest refactor priority)
echo "=== Top 10 largest Python files ==="
Get-ChildItem backend/ -Recurse -Filter *.py | Sort-Object Length -Descending | Select-Object -First 10 | Format-Table Name, Length, FullName

echo "=== Top 10 largest TypeScript files ==="
Get-ChildItem frontend/src/ -Recurse -Include *.ts,*.tsx | Sort-Object Length -Descending | Select-Object -First 10 | Format-Table Name, Length, FullName
```

**Health signal:** If `api/` has more files than `services/`, logic is leaking into routes. If `pages/` has more lines than `components/`, UI logic is not being extracted.

---

## Step 2: Dependency Direction Check

Dependencies must flow downward: `api → services → models`. Reverse imports are architectural violations.

```bash
# Routes importing from other routes (horizontal coupling — bad)
rg "from app\.api\." backend/app/api/ --type py

# Services importing from routes (upward coupling — bad)
rg "from app\.api\." backend/app/services/ --type py

# Models importing from services (upward coupling — bad)
rg "from app\.services\." backend/app/models/ --type py

# Pages importing from other pages (avoid horizontal page coupling)
rg "from.*pages/" frontend/src/components/ --type ts
rg "from.*pages/" frontend/src/hooks/ --type ts
```

All four checks must return zero results.

---

## Step 3: Service Layer Completeness

Every domain should have exactly one service owner. Check for orphaned logic.

```bash
# Domains that should have services
$expected = @("chess", "analysis", "game", "user", "engine", "coach")

foreach ($domain in $expected) {
    $found = (Get-ChildItem backend/app/services/ -Filter "*$domain*").Count
    if ($found -eq 0) {
        Write-Host "⚠ No service file found for domain: $domain" -ForegroundColor Yellow
    } else {
        Write-Host "✓ $domain service present ($found file$(if ($found -ne 1){'s'}))" -ForegroundColor Green
    }
}
```

```bash
# Logic that lives in routes but should be in a service
# (routes that do more than input validation + service call)
rg "def.*:" backend/app/api/ --type py -l | ForEach-Object {
    $lines = (Get-Content $_).Count
    if ($lines -gt 80) { Write-Host "⚠ Large route file: $_ ($lines lines) — check for inline business logic" }
}
```

---

## Step 4: Frontend Boundary Audit

```bash
# Data fetching outside the hooks layer
rg "fetch\(|axios\." frontend/src/components/ --type tsx
rg "fetch\(|axios\." frontend/src/pages/ --type tsx

# Business logic outside hooks or lib
rg "\.filter\(|\.reduce\(|\.map\(.*=>" frontend/src/pages/ --type tsx | wc -l
# > 10 transformations in pages = logic not extracted to hooks

# Type definitions scattered outside types/
rg "^(type|interface) [A-Z]" frontend/src/components/ --type ts
rg "^(type|interface) [A-Z]" frontend/src/pages/ --type ts
# Both should return 0 — all types go in frontend/src/types/
```

---

## Step 5: Chess-Specific Integrity Checks

```bash
# Single source of truth: Stockfish wrapper
echo "=== Stockfish access points (should be 1: engine_pool.py) ==="
rg "popen_uci|SimpleEngine|asyncio.*engine" backend/ --type py -l

# Single source of truth: LLM calls
echo "=== LLM call sites (should be 1: chess_coach.py) ==="
rg "openai\.|anthropic\.|ollama\." backend/ --type py -l

# Single source of truth: PGN/FEN parsing
echo "=== chess.Board instantiation (should be service layer only) ==="
rg "chess\.Board\(\)" backend/ --type py -l

# Single source of truth: game fetching
echo "=== external API calls (should be chesscom_api.py or lichess_api.py) ==="
rg "requests\.(get|post)" backend/app/ --type py -l | rg -v "test_|conftest"
```

For each group: one file is correct. Two or more files = duplication that needs consolidation.

---

## Step 6: Technical Debt Inventory

```bash
# TODO / FIXME / HACK comments = explicit debt
echo "=== Technical debt markers ==="
rg "TODO|FIXME|HACK|XXX|TEMP|NOCOMMIT" backend/ frontend/src/ --type py --type ts | wc -l

rg "TODO|FIXME|HACK" backend/ --type py
rg "TODO|FIXME|HACK" frontend/src/ --type ts

# Commented-out code blocks
echo "=== Commented-out code ==="
rg "^\s*#\s*(def |class |import )" backend/app/ --type py
rg "^\s*//\s*(const |function |import )" frontend/src/ --type ts
```

---

## Step 7: Test Coverage Signal

```bash
# Backend: service files without a corresponding test file
Get-ChildItem backend/app/services/ -Filter *.py | ForEach-Object {
    $testFile = "backend/tests/test_$($_.Name)"
    if (-not (Test-Path $testFile)) {
        Write-Host "⚠ No test file for: $($_.Name) → expected: $testFile" -ForegroundColor Yellow
    }
}

# Frontend: components without tests
Get-ChildItem frontend/src/components/ -Recurse -Filter *.tsx | ForEach-Object {
    $base = $_.BaseName
    $testPath = "frontend/src/components/__tests__/$base.test.tsx"
    $altPath  = $_.DirectoryName + "/$base.test.tsx"
    if (-not (Test-Path $testPath) -and -not (Test-Path $altPath)) {
        Write-Host "⚠ No test for: $($_.Name)" -ForegroundColor DarkYellow
    }
}
```

---

## Step 8: Findings Report

After running all steps, produce a structured report:

```markdown
## Architecture Review — ChessIQ — <date>

### Scores

| Area | Status | Notes |
|------|--------|-------|
| Dependency direction | ✅ Clean | No upward imports |
| Service completeness | ⚠ Gap | No dedicated `user_service.py` |
| Frontend boundaries | ✅ Clean | All fetching in hooks |
| Chess-specific integrity | ⚠ Drift | PGN parsing in 2 locations |
| Technical debt markers | ⚠ 7 TODOs | 3 in chess_service.py |
| Test coverage | ⚠ Gap | 4 service files untested |

### Structural counts

- Backend: 8 route files, 6 service files, 4 task files, 5 model files
- Frontend: 14 components, 9 pages, 6 hooks, 4 lib files

### Top 3 architectural debt items (prioritise for next sprint)

1. **`chess_service.py` (420 lines)** — Exceeds 300-line limit. Split into `pgn_parser.py` + `position_service.py`.
2. **PGN parsing in 2 locations** — `chess_service.py:82` and `analysis.py:44`. Consolidate to `pgn_parser.py`.
3. **No `user_service.py`** — User logic scattered across route handlers. Extract to a service.

### Accepted drift (intentional)

- `engine_pool.py` directly calls `popen_uci` — correct, this IS the pool. Exempt.

### Action items

- [ ] Split `chess_service.py`
- [ ] Consolidate PGN parsing
- [ ] Create `user_service.py`
- [ ] Add tests for `analysis_service.py` and `coach_service.py`
```

---

## Frequency

| Review type | Frequency |
|-------------|-----------|
| Structural inventory (Steps 1–2) | Monthly |
| Full audit (Steps 1–8) | Quarterly or after a sprint with heavy AI code generation |
| Chess-specific integrity (Step 5) | Before every `staging → main` release |
| Technical debt snapshot (Step 6) | Start of every sprint |
