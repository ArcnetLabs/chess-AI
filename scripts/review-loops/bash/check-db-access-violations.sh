#!/usr/bin/env bash
# Detect database-access boundary violations.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
require_rg

REPORT="${REPORT:-0}"
[[ "${1:-}" == "--report" ]] && REPORT=1

echo "ChessIQ — DB Access Violations Check"
echo "====================================="

section "DB-1 — SessionLocal imported in API routes"
run_check "DB-1" \
  "SessionLocal imported in backend/app/api/" \
  "Use 'db: Session = Depends(get_db)' or a 'with background_db_session()' helper." \
  "from .*core\.database import .*SessionLocal" \
  "backend/app/api/" --type py

section "DB-2 — supabase.from() in components / pages"
run_check "DB-2" \
  "supabase.from(...) calls in frontend components or pages" \
  "Wrap Supabase reads in /lib/supabase/queries/ helpers or call backend API." \
  "supabase\.from\(" \
  "frontend/src/components/" "frontend/src/pages/" -g "*.ts" -g "*.tsx"

section "DB-3 — SessionLocal() invoked outside core/database.py"
filtered="$(rg --line-number "SessionLocal\(\)" backend/app/ --type py 2>/dev/null \
  | grep -v "core/database.py" \
  | grep -v "alembic" || true)"
if [[ -n "$filtered" ]]; then
  count="$(echo "$filtered" | wc -l | tr -d ' ')"
  echo "  ${YELLOW}⚠ DB-3 WARN${RESET} ($count): SessionLocal() invoked outside core/database.py"
  while IFS= read -r l; do echo "    $l"; done <<< "$filtered"
  WARNINGS_COUNT=$((WARNINGS_COUNT + 1))
  WARNINGS_LINES+=("DB-3|SessionLocal() outside core/database.py|$count|Inject sessions or use background_db_session()|$filtered")
else
  echo "  ${GREEN}✓ DB-3 PASS${RESET}: SessionLocal() only used inside core/database.py"
fi

section "DB-4 — Raw SQL in routes"
CHECK_WARN=1 run_check "DB-4" \
  "Raw SQL inside route handlers" \
  "Move raw SQL into a service / repository module." \
  "db\.execute\(text\(|session\.execute\(text\(" \
  "backend/app/api/" --type py
unset CHECK_WARN

section "DB-5 — Mixed ORM patterns"
sqlalchemy="$(rg --files-with-matches "from sqlalchemy" backend/app/ --type py 2>/dev/null || true)"
supapy="$(rg --files-with-matches "from supabase import" backend/app/ --type py 2>/dev/null || true)"
overlap=""
if [[ -n "$sqlalchemy" && -n "$supapy" ]]; then
  overlap="$(comm -12 <(echo "$sqlalchemy" | sort) <(echo "$supapy" | sort) || true)"
fi
if [[ -n "$overlap" ]]; then
  count="$(echo "$overlap" | wc -l | tr -d ' ')"
  echo "  ${YELLOW}⚠ DB-5 WARN${RESET} ($count): Files mixing SQLAlchemy + supabase-py"
  echo "$overlap" | while read -r l; do echo "    $l"; done
  WARNINGS_COUNT=$((WARNINGS_COUNT + 1))
  WARNINGS_LINES+=("DB-5|Mixed SQLAlchemy + supabase-py|$count|Pick one persistence boundary per module|$overlap")
else
  echo "  ${GREEN}✓ DB-5 PASS${RESET}: No mixed ORM modules"
fi

echo
echo "═══════════════════════════════════════"
if [[ "$VIOLATIONS_COUNT" -eq 0 && "$WARNINGS_COUNT" -eq 0 ]]; then
  echo "${GREEN}DB ACCESS: ALL CLEAN ✓${RESET}"
elif [[ "$VIOLATIONS_COUNT" -eq 0 ]]; then
  echo "${YELLOW}DB ACCESS: $WARNINGS_COUNT WARNING(S) ⚠${RESET}"
else
  echo "${RED}DB ACCESS: $VIOLATIONS_COUNT VIOLATION(S) ✗${RESET}"
fi
write_report "db-access"

[[ "$VIOLATIONS_COUNT" -gt 0 ]] && exit 1 || exit 0
