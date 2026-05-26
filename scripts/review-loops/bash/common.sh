#!/usr/bin/env bash
# Shared helpers for ChessIQ review-loop bash scripts.
# Each check script sources this file and uses run_check + write_report.

set -uo pipefail

# Colours (no-op if NO_COLOR is set)
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'
  CYAN=$'\033[36m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; DIM=''; RESET=''
fi

# Globals populated by run_check
VIOLATIONS_COUNT=0
WARNINGS_COUNT=0
declare -a VIOLATIONS_LINES=()   # serialised "ID|Description|Count|Fix|Matches"
declare -a WARNINGS_LINES=()

section() {
  echo
  echo "${CYAN}── $* ──${RESET}"
}

# run_check ID DESCRIPTION FIX "rg-arg1" "rg-arg2" ...
# Optional: set CHECK_WARN=1 in caller to downgrade to warning.
# Optional: set CHECK_THRESHOLD=N to allow up to N matches.
run_check() {
  local id="$1"; shift
  local description="$1"; shift
  local fix="$1"; shift
  local threshold="${CHECK_THRESHOLD:-0}"
  local warn="${CHECK_WARN:-0}"

  local output
  output="$(rg --line-number "$@" 2>/dev/null || true)"
  local count
  count="$([[ -z "$output" ]] && echo 0 || echo "$output" | wc -l | tr -d ' ')"

  if [[ "$count" -le "$threshold" ]]; then
    echo "  ${GREEN}✓ $id PASS${RESET}: $description ($count ≤ $threshold)"
    return 0
  fi

  if [[ "$warn" == "1" ]]; then
    echo "  ${YELLOW}⚠ $id WARN${RESET} ($count > $threshold): $description"
    while IFS= read -r line; do echo "    ${DIM}$line${RESET}"; done <<< "$output"
    echo "  ${YELLOW}→ Fix:${RESET} $fix"
    WARNINGS_COUNT=$((WARNINGS_COUNT + 1))
    WARNINGS_LINES+=("$id|$description|$count|$fix|$output")
  else
    echo "  ${RED}✗ $id FAIL${RESET} ($count > $threshold): $description"
    while IFS= read -r line; do echo "    ${RED}$line${RESET}"; done <<< "$output"
    echo "  ${YELLOW}→ Fix:${RESET} $fix"
    VIOLATIONS_COUNT=$((VIOLATIONS_COUNT + 1))
    VIOLATIONS_LINES+=("$id|$description|$count|$fix|$output")
  fi
}

# write_report SCRIPT_NAME REPORT_DIR  (called only if REPORT=1)
write_report() {
  local script_name="$1"
  local report_dir="${2:-docs/review-reports}"
  [[ "${REPORT:-0}" == "1" ]] || return 0

  mkdir -p "$report_dir"
  local stamp; stamp="$(date '+%Y-%m-%d-%H%M')"
  local out="$report_dir/${script_name}-${stamp}.md"

  {
    echo "# ${script_name} Report"
    echo
    echo "Generated: $(date -Iseconds)"
    echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    echo

    if [[ "$VIOLATIONS_COUNT" -eq 0 && "$WARNINGS_COUNT" -eq 0 ]]; then
      echo "✅ No violations or warnings."
    else
      if [[ "$VIOLATIONS_COUNT" -gt 0 ]]; then
        echo "## Hard violations"
        for entry in "${VIOLATIONS_LINES[@]}"; do
          IFS='|' read -r id desc count fix matches <<< "$entry"
          echo
          echo "### $id — $desc"
          echo "- **Count:** $count"
          echo "- **Fix:** $fix"
          echo
          echo '```'
          echo "$matches"
          echo '```'
        done
      fi
      if [[ "$WARNINGS_COUNT" -gt 0 ]]; then
        echo
        echo "## Warnings"
        for entry in "${WARNINGS_LINES[@]}"; do
          IFS='|' read -r id desc count fix matches <<< "$entry"
          echo
          echo "### $id — $desc"
          echo "- **Count:** $count"
          echo "- **Fix:** $fix"
          echo
          echo '```'
          echo "$matches"
          echo '```'
        done
      fi
    fi
  } > "$out"

  echo "  ${CYAN}Report: $out${RESET}"
}

require_rg() {
  if ! command -v rg >/dev/null 2>&1; then
    echo "${RED}ripgrep (rg) is required for review-loop scripts.${RESET}" >&2
    echo "  Install: https://github.com/BurntSushi/ripgrep#installation" >&2
    exit 2
  fi
}
