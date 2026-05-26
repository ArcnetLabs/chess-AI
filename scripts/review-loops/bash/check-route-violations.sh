#!/usr/bin/env bash
# Detect route-layer boundary violations.
# Bash port of check-route-violations.ps1.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
require_rg

REPORT="${REPORT:-0}"
[[ "${1:-}" == "--report" ]] && REPORT=1

echo "ChessIQ — Route Layer Violations Check"
echo "======================================="

section "RT-1 — SessionLocal imported in API routes"
run_check "RT-1" \
  "Direct SessionLocal import in api/ (bypasses Depends(get_db))" \
  "Use 'db: Session = Depends(get_db)' or 'with background_db_session()' helper" \
  "from .*core\.database import .*SessionLocal" \
  "backend/app/api/" --type py

section "RT-2 — Engine import in API routes"
run_check "RT-2" \
  "StockfishEngine / engine_pool imports inside api/ files" \
  "Routes must not import the engine layer. Inject via FastAPI Depends() or call service functions." \
  "from .*services\.engine.*import" \
  "backend/app/api/" --type py

section "RT-3 — UnifiedChessAnalyzer instantiated in routes"
CHECK_WARN=1 run_check "RT-3" \
  "UnifiedChessAnalyzer instantiated directly in routes" \
  "Routes call a service function. The service constructs the analyzer." \
  "UnifiedChessAnalyzer\(" \
  "backend/app/api/" --type py
unset CHECK_WARN

section "RT-4 — Direct axios calls in components / pages"
run_check "RT-4" \
  "axios.get/post/put/delete/patch in components or pages" \
  "All HTTP calls must go through frontend/src/lib/api.ts" \
  "axios\.(get|post|put|delete|patch)\(" \
  "frontend/src/components/" "frontend/src/pages/" -g "*.ts" -g "*.tsx"

section "RT-5 — fetch() in components / pages"
CHECK_WARN=1 run_check "RT-5" \
  "fetch( in components or pages — should go through lib/api.ts" \
  "Centralise HTTP access in lib/api.ts." \
  "\bfetch\(" \
  "frontend/src/components/" "frontend/src/pages/" -g "*.ts" -g "*.tsx"
unset CHECK_WARN

section "RT-6 — HTTP calls inside Celery tasks"
run_check "RT-6" \
  "requests.* / httpx.* in backend/app/tasks/" \
  "Celery tasks must invoke service-layer functions, not call backend HTTP endpoints." \
  "requests\.(get|post|put|delete)|httpx\.(get|post|put|delete|AsyncClient)" \
  "backend/app/tasks/" --type py

section "RT-7 — Inline LLM calls in routes / tasks"
run_check "RT-7" \
  "openai./anthropic. inline calls in routes or tasks" \
  "All LLM access must go through services/integration/ai_client.py." \
  "openai\.|anthropic\.|ollama\.generate" \
  "backend/app/api/" "backend/app/tasks/" --type py

echo
echo "═══════════════════════════════════════"
if [[ "$VIOLATIONS_COUNT" -eq 0 ]]; then
  echo "${GREEN}ROUTE CHECK: ALL CLEAN ✓${RESET}"
  write_report "route-violations"
  exit 0
else
  echo "${RED}ROUTE CHECK: $VIOLATIONS_COUNT VIOLATION(S) ✗${RESET}"
  write_report "route-violations"
  exit 1
fi
