#!/usr/bin/env bash
# Detect missing authentication guards on mutating API routes.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
require_rg

REPORT="${REPORT:-0}"
[[ "${1:-}" == "--report" ]] && REPORT=1

echo "ChessIQ — Authentication Guards Check"
echo "======================================"

# AG-1 — Per-file: mutating route file without Depends(get_current_user)
section "AG-1 — Mutating routes missing Depends(get_current_user)"
unguarded=()
if [[ -d backend/app/api ]]; then
  while IFS= read -r f; do
    [[ "$(basename "$f")" == "__init__.py" ]] && continue
    if grep -Eq '@router\.(post|put|delete|patch)\(' "$f"; then
      if ! grep -q 'Depends(get_current_user' "$f"; then
        unguarded+=("$f")
      fi
    fi
  done < <(find backend/app/api -type f -name '*.py')
fi
if [[ "${#unguarded[@]}" -eq 0 ]]; then
  echo "  ${GREEN}✓ AG-1 PASS${RESET}: Every mutating route file uses Depends(get_current_user)"
else
  count="${#unguarded[@]}"
  echo "  ${RED}✗ AG-1 FAIL${RESET} ($count): Mutating endpoints with no auth guard"
  printf '    %s\n' "${unguarded[@]}"
  echo "  ${YELLOW}→ Fix:${RESET} Add 'current_user: User = Depends(get_current_user)' to each handler"
  VIOLATIONS_COUNT=$((VIOLATIONS_COUNT + 1))
  joined="$(printf '%s\n' "${unguarded[@]}")"
  VIOLATIONS_LINES+=("AG-1|Route files declare mutating endpoints without auth dependency|$count|Add Depends(get_current_user) to each handler|$joined")
fi

# AG-2 — Files that import get_current_user but never use it
section "AG-2 — Imported but unused auth dependency"
unused=()
if [[ -d backend/app/api ]]; then
  while IFS= read -r f; do
    if grep -Eq 'from .*auth_middleware import .*get_current_user' "$f"; then
      if ! grep -q 'Depends(get_current_user' "$f"; then
        unused+=("$f")
      fi
    fi
  done < <(find backend/app/api -type f -name '*.py')
fi
if [[ "${#unused[@]}" -eq 0 ]]; then
  echo "  ${GREEN}✓ AG-2 PASS${RESET}: No unused auth imports"
else
  count="${#unused[@]}"
  echo "  ${RED}✗ AG-2 FAIL${RESET} ($count): get_current_user imported but never used"
  printf '    %s\n' "${unused[@]}"
  VIOLATIONS_COUNT=$((VIOLATIONS_COUNT + 1))
  joined="$(printf '%s\n' "${unused[@]}")"
  VIOLATIONS_LINES+=("AG-2|get_current_user imported but not used|$count|Either use Depends(get_current_user) or remove the import|$joined")
fi

# AG-3 — Defined but imported nowhere
section "AG-3 — get_current_user defined but imported nowhere"
defined="$(rg --files-with-matches "def get_current_user\b" backend/app/ --type py 2>/dev/null || true)"
imported="$(rg --files-with-matches "from .*auth_middleware.*get_current_user|Depends\(get_current_user" backend/app/ --type py 2>/dev/null || true)"
if [[ -n "$defined" && -z "$imported" ]]; then
  echo "  ${RED}✗ AG-3 FAIL${RESET}: get_current_user defined in $defined but imported by zero files"
  VIOLATIONS_COUNT=$((VIOLATIONS_COUNT + 1))
  VIOLATIONS_LINES+=("AG-3|get_current_user defined but never imported|1|Wire Depends(get_current_user) into every mutating route|$defined")
else
  echo "  ${GREEN}✓ AG-3 PASS${RESET}: get_current_user is referenced"
fi

# AG-4 — getSession() used for AUTHORIZATION (security anti-pattern)
# Narrowed to lib/auth/ + middleware — forwarding the token from lib/api.ts is fine.
section "AG-4 — getSession() in frontend SSR / lib/auth code"
run_check "AG-4" \
  "supabase.auth.getSession() used for SSR authorization (reads unvalidated cookie)" \
  "Replace with supabase.auth.getUser() — getUser validates the JWT" \
  "supabase\.auth\.getSession\(\)" \
  "frontend/src/lib/auth/" "frontend/src/middleware.ts"

# AG-5 — Manual Authorization header parsing
section "AG-5 — Manual Authorization header parsing in routes"
run_check "AG-5" \
  "Raw request.headers Authorization parsing in routes" \
  "Use Depends(get_current_user) instead of parsing the header manually" \
  'request\.headers\.get\(["'"'"']Authorization["'"'"']\)|request\.headers\[["'"'"']Authorization["'"'"']\]' \
  "backend/app/api/" --type py

# AG-6 — {user_id} routes without ownership reference
section "AG-6 — {user_id} routes without ownership reference"
ownership=()
if [[ -d backend/app/api ]]; then
  while IFS= read -r f; do
    if grep -Eq '@router\.(get|put|delete|post|patch)\(["'"'"'][^"'"'"']*\{user_id' "$f"; then
      if ! grep -q 'current_user' "$f"; then
        ownership+=("$f")
      fi
    fi
  done < <(find backend/app/api -type f -name '*.py')
fi
if [[ "${#ownership[@]}" -eq 0 ]]; then
  echo "  ${GREEN}✓ AG-6 PASS${RESET}: All {user_id} routes reference current_user"
else
  count="${#ownership[@]}"
  echo "  ${RED}✗ AG-6 FAIL${RESET} ($count): {user_id} routes without ownership reference"
  printf '    %s\n' "${ownership[@]}"
  VIOLATIONS_COUNT=$((VIOLATIONS_COUNT + 1))
  joined="$(printf '%s\n' "${ownership[@]}")"
  VIOLATIONS_LINES+=("AG-6|{user_id} routes lack ownership verification|$count|After Depends(get_current_user), verify current_user.id == user_id|$joined")
fi

echo
echo "═══════════════════════════════════════"
if [[ "$VIOLATIONS_COUNT" -eq 0 ]]; then
  echo "${GREEN}AUTH GUARDS: ALL CLEAN ✓${RESET}"
  write_report "auth-guards"
  exit 0
else
  echo "${RED}AUTH GUARDS: $VIOLATIONS_COUNT VIOLATION(S) ✗${RESET}"
  write_report "auth-guards"
  exit 1
fi
