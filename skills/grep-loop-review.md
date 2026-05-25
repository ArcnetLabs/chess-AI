# Skill: Grep Loop Review

**When to use:** After implementing any feature or before merging any PR. Run a systematic grep-based inspection to find architecture violations, duplicate logic, and naming inconsistencies — before a human code review.

---

## The Core Loop

```
1. Run the grep suite below
2. Triage each finding (real violation / false positive / acceptable exception)
3. Fix real violations
4. Re-run affected grep checks
5. Repeat until all checks are clean
6. Document any accepted exceptions inline in the code
```

---

## Full Grep Suite

Run these from the repo root. Each section is independent — run all of them.

### A. Architecture Violations

```bash
# Stockfish access outside the engine pool
echo "=== A1: Stockfish outside pool ==="
rg "SimpleEngine|popen_uci|chess\.engine\." backend/app/api/ backend/app/tasks/ --type py

# Inline LLM calls outside chat service
echo "=== A2: Inline LLM calls ==="
rg "openai\.|anthropic\.|requests\.post.*completions\|ollama\.generate" backend/app/api/ backend/app/tasks/ --type py

# Direct DB session import in routes (bypasses dependency injection)
echo "=== A3: Direct SessionLocal in routes ==="
rg "from app\.core\.database import SessionLocal" backend/app/api/ --type py

# Service role key anywhere in frontend
echo "=== A4: service_role in frontend ==="
rg "service_role|SERVICE_ROLE|supabaseServiceRole" frontend/src/

# getSession() for server-side auth (unvalidated cookie read)
echo "=== A5: getSession in server code ==="
rg "getSession\(\)" frontend/src/pages/ frontend/src/lib/
```

### B. Duplicate Logic

```bash
# Multiple fetch/game-fetching implementations
echo "=== B1: Duplicate game-fetching ==="
rg "def.*fetch.*game|def.*get.*game" backend/app/ --type py

# Repeated analysis logic outside unified_analyzer
echo "=== B2: Analysis outside unified_analyzer ==="
rg "def.*analyze.*position\|def.*evaluate.*position" backend/app/api/ backend/app/tasks/ --type py

# Multiple Stockfish depth constants
echo "=== B3: Hardcoded Stockfish depths ==="
rg "depth=\d+" backend/app/ --type py

# Direct axios calls outside api.ts
echo "=== B4: Direct axios in components/pages ==="
rg "axios\.(get|post|put|delete|patch)" frontend/src/components/ frontend/src/pages/ --type ts

# Repeated auth check pattern outside withAuth
echo "=== B5: Manual auth checks in pages ==="
rg "supabase\.auth\.getUser\(\)" frontend/src/pages/ --type ts
```

### C. Naming Inconsistencies

```bash
# Mixed naming conventions for user ID fields
echo "=== C1: user_id naming ==="
rg "userId\|user_id\|userID" backend/app/ --type py | rg -v "user_id"

# Mixed endpoint naming (camelCase vs snake_case in routes)
echo "=== C2: camelCase route params ==="
rg "@router\.(get|post|put|delete).*[a-z][A-Z]" backend/app/api/ --type py

# Mixed TypeScript naming (PascalCase interfaces vs IInterface)
echo "=== C3: I-prefix interfaces ==="
rg "interface I[A-Z]" frontend/src/ --type ts
```

### D. Security Patterns

```bash
# Hardcoded secrets or API keys
echo "=== D1: Hardcoded secrets ==="
rg "sk-|eyJhbGci|password.*=.*['\"][^$]['\"]" backend/app/ --type py

# Missing auth guard on mutating routes
echo "=== D2: Unguarded POST/PUT/DELETE routes ==="
rg "@router\.(post|put|delete|patch)" backend/app/api/ --type py -A 3 | rg -v "current_user\|Depends"

# Supabase anon key accidentally in server-side code
echo "=== D3: anon key in backend ==="
rg "anon.*key\|SUPABASE_ANON" backend/ --type py
```

### E. Database Access

```bash
# N+1 query patterns (loop with db query inside)
echo "=== E1: Potential N+1 ==="
rg "for.*in.*:\s*$" backend/app/services/ --type py -A 2 | rg "db\.(query|execute|get)"

# Missing index on foreign key columns (check migration files)
echo "=== E2: Unindexed foreign keys in migrations ==="
rg "ForeignKey\|foreign_key" backend/alembic/versions/ | rg -v "Index\|index"
```

---

## Triaging Findings

For each finding, classify:

| Class | Action |
|-------|--------|
| **Real violation** | Fix before merging |
| **Acceptable exception** | Add `# grep-exempt: <reason>` comment inline |
| **False positive** | Note it — consider refining the grep pattern |

---

## Grep Loop Prompt Template

```
Run the full grep-loop review on the changes in this PR.

Branch: <branch-name>
Relevant files: [list files changed]

For each grep section (A through E):
1. Run the grep commands.
2. Classify each finding as: real violation / acceptable exception / false positive.
3. Fix all real violations.
4. Re-run the affected check.
5. Produce a summary: N violations found, N fixed, N accepted with reason, N false positives.
```

---

## Verification Checklist

- [ ] All A-series (architecture) checks return zero real violations.
- [ ] All D-series (security) checks return zero violations.
- [ ] B-series and C-series findings triaged and documented.
- [ ] Accepted exceptions have inline comments explaining why.
- [ ] Summary produced with counts per section.
