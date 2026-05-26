#!/usr/bin/env bash
# Run the entire ChessIQ grep-loop review suite (bash port).

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

REPORT="${REPORT:-0}"
[[ "${1:-}" == "--report" ]] && REPORT=1

checks=(
  "File Sizes|check-file-sizes.sh"
  "Duplicates|check-duplicates.sh"
  "Stockfish Violations|check-stockfish-violations.sh"
  "Route Violations|check-route-violations.sh"
  "DB Access Violations|check-db-access-violations.sh"
  "Auth Guards|check-auth-guards.sh"
)

echo
echo "╔══════════════════════════════════════════════════════╗"
echo "║    ChessIQ — Full Grep-Loop Review Suite             ║"
echo "║    Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "║    Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "╚══════════════════════════════════════════════════════╝"

declare -a results=()
fail_count=0

for entry in "${checks[@]}"; do
  IFS='|' read -r name script <<< "$entry"
  echo
  echo "▶ Running: $name ($script)"
  printf '%.0s─' {1..60}; echo

  script_path="$SCRIPT_DIR/$script"
  if [[ ! -f "$script_path" ]]; then
    echo "  ${RED}✗ Script not found: $script_path${RESET}"
    results+=("$name|$script|MISSING|-1")
    continue
  fi

  if [[ "$REPORT" == "1" ]]; then
    REPORT=1 bash "$script_path"
  else
    bash "$script_path"
  fi
  code=$?

  if [[ "$code" -eq 0 ]]; then
    status="PASS"
  else
    status="FAIL"
    fail_count=$((fail_count + 1))
  fi
  results+=("$name|$script|$status|$code")
done

echo
echo "╔══════════════════════════════════════════════════════╗"
echo "║                  SUITE SUMMARY                       ║"
echo "╚══════════════════════════════════════════════════════╝"
for r in "${results[@]}"; do
  IFS='|' read -r name script status code <<< "$r"
  case "$status" in
    PASS)    glyph="✓"; colour="$GREEN" ;;
    FAIL)    glyph="✗"; colour="$RED" ;;
    *)       glyph="?"; colour="$YELLOW" ;;
  esac
  printf '  %s%s%s  %-28s %s\n' "$colour" "$glyph" "$RESET" "$name" "$status"
done

echo
if [[ "$fail_count" -eq 0 ]]; then
  echo "  ${GREEN}All checks passed. PR is structurally clean.${RESET}"
  exit 0
else
  echo "  ${RED}$fail_count check(s) failed. Address all hard violations before merging.${RESET}"
  exit 1
fi
