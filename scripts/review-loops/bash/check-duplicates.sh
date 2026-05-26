#!/usr/bin/env bash
# Detect duplicate implementations across the repository.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
require_rg

REPORT="${REPORT:-0}"
[[ "${1:-}" == "--report" ]] && REPORT=1

echo "ChessIQ — Duplicate Implementations Check"
echo "=========================================="

section "DP-1 — Duplicate AIClient class definitions"
CHECK_THRESHOLD=1 run_check "DP-1" \
  "Multiple class AIClient definitions" \
  "Keep exactly one AIClient in services/integration/ai_client.py." \
  "^class AIClient\b" "backend/app/" --type py
unset CHECK_THRESHOLD

section "DP-2 — Duplicate analyzer implementations"
CHECK_THRESHOLD=1 run_check "DP-2" \
  "Multiple analyzer classes (ChessAnalyzer / UnifiedAnalyzer / ChessAnalysis)" \
  "Keep one canonical analyzer in services/analysis/unified_analyzer.py." \
  "^class (\w*Analyzer|ChessAnalysis)\b" "backend/app/" --type py
unset CHECK_THRESHOLD

section "DP-3 — Duplicate game-fetching functions"
CHECK_THRESHOLD=1 run_check "DP-3" \
  "Multiple fetch_game / get_game function definitions" \
  "Consolidate in services/integration/chesscom_api.py." \
  "def (fetch|get)_game\b" "backend/app/" --type py
unset CHECK_THRESHOLD

section "DP-4 — Duplicate PGN parsing"
run_check "DP-4" \
  "chess.pgn / pgn.read_game called outside services/" \
  "Centralise PGN parsing in services/chess_service.py." \
  "chess\.pgn|pgn\.read_game" "backend/app/api/" "backend/app/tasks/" --type py

section "DP-5 — Duplicate Supabase client instantiation"
run_check "DP-5" \
  "createBrowserClient/createServerClient called outside lib/supabase/" \
  "Import from frontend/src/lib/supabase/." \
  "createBrowserClient|createServerClient" \
  "frontend/src/pages/" "frontend/src/components/" -g "*.ts" -g "*.tsx"

section "DP-6 — Multiple HTTP client patterns"
axios_files="$(rg --files-with-matches "^import axios|from ['\"]axios['\"]" frontend/src/ -g '*.ts' -g '*.tsx' 2>/dev/null || true)"
fetch_files="$(rg --files-with-matches "\bfetch\(" frontend/src/ -g '*.ts' -g '*.tsx' 2>/dev/null || true)"
axios_count="$([[ -z "$axios_files" ]] && echo 0 || echo "$axios_files" | wc -l | tr -d ' ')"
fetch_count="$([[ -z "$fetch_files" ]] && echo 0 || echo "$fetch_files" | wc -l | tr -d ' ')"
if [[ "$axios_count" -gt 0 && "$fetch_count" -gt 0 ]]; then
  echo "  ${YELLOW}⚠ DP-6 WARN${RESET}: axios ($axios_count files) + fetch ($fetch_count files) in use"
  WARNINGS_COUNT=$((WARNINGS_COUNT + 1))
  WARNINGS_LINES+=("DP-6|Multiple HTTP client patterns|$((axios_count + fetch_count))|Standardise on axios via lib/api.ts.|axios files: $axios_count, fetch files: $fetch_count")
else
  echo "  ${GREEN}✓ DP-6 PASS${RESET}: Single HTTP client pattern in use"
fi

section "DP-7 — Ad-hoc supabase.auth.getUser() in pages"
run_check "DP-7" \
  "Pages calling supabase.auth.getUser() manually" \
  "Use the withAuth HOC or a centralised auth hook." \
  "supabase\.auth\.getUser\(\)" \
  "frontend/src/pages/" -g "*.tsx"

section "DP-8 — Hardcoded analysis depth constants"
CHECK_THRESHOLD=2 CHECK_WARN=1 run_check "DP-8" \
  "Multiple hardcoded depth=N values" \
  "Define ANALYSIS_DEPTH in app/core/config.py and reference it everywhere." \
  "depth=\d+" "backend/app/" --type py
unset CHECK_THRESHOLD CHECK_WARN

echo
echo "═══════════════════════════════════════"
if [[ "$VIOLATIONS_COUNT" -eq 0 && "$WARNINGS_COUNT" -eq 0 ]]; then
  echo "${GREEN}DUPLICATES: ALL CLEAN ✓${RESET}"
elif [[ "$VIOLATIONS_COUNT" -eq 0 ]]; then
  echo "${YELLOW}DUPLICATES: PASSED WITH $WARNINGS_COUNT WARNING(S) ⚠${RESET}"
else
  echo "${RED}DUPLICATES: $VIOLATIONS_COUNT HARD + $WARNINGS_COUNT WARN ✗${RESET}"
fi
write_report "duplicates"

[[ "$VIOLATIONS_COUNT" -gt 0 ]] && exit 1 || exit 0
