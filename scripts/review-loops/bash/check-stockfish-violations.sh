#!/usr/bin/env bash
# Detect Stockfish instantiation outside the engine pool.
# Bash port of check-stockfish-violations.ps1.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
require_rg

REPORT="${REPORT:-0}"
[[ "${1:-}" == "--report" ]] && REPORT=1

echo "ChessIQ — Stockfish Violations Check"
echo "====================================="

section "SF-1 — chess.engine direct construction in routes / tasks"
run_check "SF-1" \
  "chess.engine.SimpleEngine / popen_uci / chess.engine. in routes or tasks" \
  "Use 'from app.services.engine.engine_pool import get_engine_pool' and call pool.analyze(board, depth=15)" \
  "SimpleEngine|popen_uci|chess\.engine\.SimpleEngine" \
  "backend/app/api/" "backend/app/tasks/" --type py

section "SF-2 — StockfishEngine() in route handlers"
run_check "SF-2" \
  "StockfishEngine(...) instantiated in route handlers" \
  "Routes must never construct engines. Receive the pool via Depends() and call pool.analyze()." \
  "StockfishEngine\(" "backend/app/api/" --type py

section "SF-3 — StockfishEngine() in services outside engine module"
matches="$(rg --line-number "StockfishEngine\(" backend/app/services/ --type py 2>/dev/null \
  | grep -v "engine/engine_pool.py" \
  | grep -v "engine/stockfish_engine.py" || true)"
if [[ -n "$matches" ]]; then
  count="$(echo "$matches" | wc -l | tr -d ' ')"
  echo "  ${RED}✗ SF-3 FAIL${RESET} ($count): StockfishEngine instantiated outside engine module"
  while IFS= read -r l; do echo "    $l"; done <<< "$matches"
  echo "  ${YELLOW}→ Fix:${RESET} Accept the engine pool via constructor injection in services"
  VIOLATIONS_COUNT=$((VIOLATIONS_COUNT + 1))
  VIOLATIONS_LINES+=("SF-3|StockfishEngine instantiated outside engine module|$count|Accept the engine pool via constructor injection|$matches")
else
  echo "  ${GREEN}✓ SF-3 PASS${RESET}: StockfishEngine only constructed inside engine module"
fi

section "SF-4 — Hardcoded stockfish path strings"
run_check "SF-4" \
  "Hardcoded /usr/games/stockfish or /usr/bin/stockfish paths in source" \
  "Use settings.STOCKFISH_PATH from app.core.config (env-driven)" \
  "['\"]/usr/(games|bin)/stockfish['\"]" \
  "backend/app/" --type py

section "SF-5 — stockfish python package direct import"
run_check "SF-5" \
  "from stockfish import Stockfish (the package — bypasses pool)" \
  "Use app.services.engine.engine_pool instead" \
  "^from stockfish import|^import stockfish\b" \
  "backend/app/" --type py

# Summary
echo
echo "═══════════════════════════════════════"
if [[ "$VIOLATIONS_COUNT" -eq 0 ]]; then
  echo "${GREEN}STOCKFISH CHECK: ALL CLEAN ✓${RESET}"
  write_report "stockfish-violations"
  exit 0
else
  echo "${RED}STOCKFISH CHECK: $VIOLATIONS_COUNT VIOLATION(S) ✗${RESET}"
  write_report "stockfish-violations"
  exit 1
fi
