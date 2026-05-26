#!/usr/bin/env bash
# Enforce per-file size limits across the repository.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

REPORT="${REPORT:-0}"
[[ "${1:-}" == "--report" ]] && REPORT=1

HARD_HITS=0
WARN_HITS=0
declare -a HARD_LINES=()
declare -a WARN_LINES=()

check_sizes() {
  local id="$1" desc="$2" path="$3" pattern="$4" warn_limit="$5" hard_limit="$6" fix="$7"
  echo
  echo "${CYAN}── $id — $desc (warn $warn_limit, hard $hard_limit) ──${RESET}"
  if [[ ! -d "$path" ]]; then
    echo "  ${YELLOW}? $id SKIP${RESET}: $path missing"
    return
  fi
  local files_hard=() files_warn=()
  while IFS= read -r f; do
    local lc; lc="$(wc -l < "$f" | tr -d ' ')"
    if [[ "$lc" -gt "$hard_limit" ]]; then
      files_hard+=("$f|$lc")
    elif [[ "$lc" -gt "$warn_limit" ]]; then
      files_warn+=("$f|$lc")
    fi
  done < <(find "$path" -type f -name "$pattern")

  if [[ "${#files_hard[@]}" -eq 0 && "${#files_warn[@]}" -eq 0 ]]; then
    echo "  ${GREEN}✓ $id PASS${RESET}: all files within limits"
    return
  fi

  for entry in "${files_hard[@]}"; do
    IFS='|' read -r f lc <<< "$entry"
    echo "  ${RED}✗ $id FAIL HARD${RESET} ($lc > $hard_limit): $f"
    HARD_HITS=$((HARD_HITS + 1))
    HARD_LINES+=("$id|$desc|$f|$lc|$fix")
  done
  for entry in "${files_warn[@]}"; do
    IFS='|' read -r f lc <<< "$entry"
    echo "  ${YELLOW}⚠ $id WARN${RESET} ($lc > $warn_limit): $f"
    WARN_HITS=$((WARN_HITS + 1))
    WARN_LINES+=("$id|$desc|$f|$lc|$fix")
  done
  echo "  ${YELLOW}→ Fix:${RESET} $fix"
}

echo "ChessIQ — File Size Limits Check"
echo "================================="

check_sizes "FS-1" "Python service files" \
  "backend/app/services" "*.py" 250 300 \
  "Split into focused modules. Mixed responsibilities almost always cause this."

check_sizes "FS-2" "Python route files" \
  "backend/app/api" "*.py" 200 250 \
  "Routes should be thin. Move business logic into services. Split by sub-resource."

check_sizes "FS-3" "Python Celery task files" \
  "backend/app/tasks" "*.py" 200 250 \
  "Tasks orchestrate services. If a task grows, the logic belongs in a service."

check_sizes "FS-4" "React components" \
  "frontend/src/components" "*.tsx" 200 300 \
  "Extract sub-components. Move data fetching to hooks."

check_sizes "FS-5" "Next.js pages" \
  "frontend/src/pages" "*.tsx" 100 150 \
  "Pages compose components — they should not contain business logic."

check_sizes "FS-6" "Frontend lib files" \
  "frontend/src/lib" "*.ts" 200 250 \
  "Split by domain (api/users.ts + api/games.ts + api/analysis.ts)."

echo
echo "═══════════════════════════════════════"
if [[ "$HARD_HITS" -eq 0 && "$WARN_HITS" -eq 0 ]]; then
  echo "${GREEN}FILE SIZES: ALL CLEAN ✓${RESET}"
elif [[ "$HARD_HITS" -eq 0 ]]; then
  echo "${YELLOW}FILE SIZES: $WARN_HITS WARNING(S) (no hard violations) ⚠${RESET}"
else
  echo "${RED}FILE SIZES: $HARD_HITS HARD + $WARN_HITS WARNING ✗${RESET}"
fi

if [[ "$REPORT" == "1" ]]; then
  mkdir -p docs/review-reports
  stamp="$(date '+%Y-%m-%d-%H%M')"
  out="docs/review-reports/file-sizes-${stamp}.md"
  {
    echo "# File Sizes Report"
    echo
    echo "Generated: $(date -Iseconds)"
    echo
    if [[ "$HARD_HITS" -gt 0 ]]; then
      echo "## Hard violations"
      echo
      echo "| ID | File | Lines | Fix |"
      echo "|----|------|-------|-----|"
      for entry in "${HARD_LINES[@]}"; do
        IFS='|' read -r id desc f lc fix <<< "$entry"
        echo "| $id | $f | $lc | $fix |"
      done
    fi
    if [[ "$WARN_HITS" -gt 0 ]]; then
      echo
      echo "## Warnings"
      echo
      echo "| ID | File | Lines |"
      echo "|----|------|-------|"
      for entry in "${WARN_LINES[@]}"; do
        IFS='|' read -r id desc f lc fix <<< "$entry"
        echo "| $id | $f | $lc |"
      done
    fi
    if [[ "$HARD_HITS" -eq 0 && "$WARN_HITS" -eq 0 ]]; then
      echo "✅ No violations or warnings."
    fi
  } > "$out"
  echo "  ${CYAN}Report: $out${RESET}"
fi

[[ "$HARD_HITS" -gt 0 ]] && exit 1 || exit 0
