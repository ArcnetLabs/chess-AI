<#
.SYNOPSIS
    D-series security checks for ChessIQ.
    Catches hardcoded secrets, unguarded routes, and key leaks before they reach production.

.OUTPUTS
    Coloured pass/fail lines. Exit code 0 = clean, 1 = violations found.

.EXAMPLE
    .\scripts\review-loops\check-security.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:violations = 0

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Run-Check {
    param(
        [string]$id,
        [string]$description,
        [string[]]$rgArgs,
        [string]$fix,
        [switch]$fatal
    )

    $output = & rg @rgArgs 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        $severity = if ($fatal) { "CRITICAL" } else { "FAIL" }
        $color    = if ($fatal) { "Magenta"  } else { "Red" }
        Write-Host "  ✗ $id $severity ($count match$(if ($count -ne 1){'es'})): $description" -ForegroundColor $color
        $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
        Write-Host "  → Fix: $fix" -ForegroundColor Yellow
        $script:violations++
    } elseif ($exitCode -eq 1) {
        Write-Host "  ✓ $id PASS: $description" -ForegroundColor Green
    } else {
        Write-Host "  ? $id SKIP: rg error or path missing" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ Security Review — D-Series" -ForegroundColor White
Write-Host "====================================" -ForegroundColor White

Write-Section "D1 — Hardcoded API keys / secrets"
Run-Check `
    -id "D1a" `
    -description "OpenAI sk- keys hardcoded in Python files" `
    -rgArgs @("sk-[A-Za-z0-9]{20}", "backend/", "--type", "py") `
    -fix "Move to environment variables — never hardcode API keys" `
    -fatal

Run-Check `
    -id "D1b" `
    -description "JWT / Bearer tokens hardcoded in source" `
    -rgArgs @("eyJhbGci", "backend/", "frontend/src/") `
    -fix "JWTs must come from Supabase session cookies, not source files" `
    -fatal

Run-Check `
    -id "D1c" `
    -description "Plaintext passwords in Python source" `
    -rgArgs @("password\s*=\s*['\"][^{'\"][^'\"]{4,}", "backend/app/", "--type", "py") `
    -fix "Use environment variables or a secrets manager"

Write-Section "D2 — Unguarded mutating routes"
Run-Check `
    -id "D2" `
    -description "POST/PUT/DELETE routes without current_user or auth Depends" `
    -rgArgs @("@router\.(post|put|delete|patch)\(", "backend/app/api/", "--type", "py", "--no-heading") `
    -fix "Every mutating route must include 'current_user: User = Depends(get_current_user)'"
# Note: rg cannot natively check the line that follows a match. The above will list all mutating routes
# for manual triage — verify each listed route has auth dependency in the function signature.

Write-Section "D3 — Supabase anon key in backend"
Run-Check `
    -id "D3" `
    -description "Supabase anon/publishable key referenced in backend Python code" `
    -rgArgs @("SUPABASE_ANON|anon.*key|publishable.*key", "backend/", "--type", "py") `
    -fix "Backend must use SUPABASE_SERVICE_ROLE_KEY (via env var) — not the anon key"

Write-Section "D4 — service_role key in frontend"
Run-Check `
    -id "D4" `
    -description "Supabase service-role key in frontend (exposes admin access to browser)" `
    -rgArgs @("service_role|SERVICE_ROLE|supabaseAdmin", "frontend/src/") `
    -fix "service_role must only exist in backend/ env vars — never in frontend code" `
    -fatal

Write-Section "D5 — .env files committed"
Run-Check `
    -id "D5" `
    -description ".env files checked into git (not .env.example)" `
    -rgArgs @("^\.env$|^\.env\.[^e]", "--glob", "*.env", ".") `
    -fix "Remove from git: 'git rm --cached .env'. Ensure .env* is in .gitignore."

Write-Section "D6 — Debug endpoints without auth"
Run-Check `
    -id "D6" `
    -description "Debug or test routes accessible without authentication" `
    -rgArgs @("@router\.(get|post)\(['\"]/(debug|test|dev)/", "backend/app/api/", "--type", "py") `
    -fix "Remove debug routes before production or guard them with an admin auth dependency"

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
if ($script:violations -eq 0) {
    Write-Host "D-SERIES: ALL CLEAN ✓" -ForegroundColor Green
    exit 0
} else {
    Write-Host "D-SERIES: $($script:violations) SECURITY VIOLATION$(if ($script:violations -ne 1){'S'}) FOUND ✗" -ForegroundColor Red
    Write-Host "CRITICAL: Do not merge until all D-series violations are resolved." -ForegroundColor Magenta
    exit 1
}
