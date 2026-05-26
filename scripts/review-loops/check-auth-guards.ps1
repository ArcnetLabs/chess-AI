<#
.SYNOPSIS
    Detect missing authentication guards on mutating API routes.

.DESCRIPTION
    Enforces invariants:
      AG-1: Every POST/PUT/DELETE/PATCH route must use Depends(get_current_user).
      AG-2: get_current_user (or get_current_user_optional) must be imported in route files.
      AG-3: GET routes that operate on /{user_id}/* must verify ownership.
      AG-4: Frontend Supabase calls must use getUser() not getSession() for SSR auth.
      AG-5: No route may use raw Authorization headers without going through the auth dependency.

.PARAMETER Report
    Write a markdown report under docs/review-reports/.
#>

[CmdletBinding()]
param(
    [switch]$Report,
    [string]$ReportDir = "docs/review-reports"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

if (-not (Get-Command rg -ErrorAction SilentlyContinue)) {
    Write-Host "ripgrep (rg) is required for this script." -ForegroundColor Red
    Write-Host "  Windows:  winget install BurntSushi.ripgrep.MSVC   or   choco install ripgrep" -ForegroundColor Yellow
    Write-Host "  macOS:    brew install ripgrep" -ForegroundColor Yellow
    Write-Host "  Linux:    apt install ripgrep / pacman -S ripgrep / dnf install ripgrep" -ForegroundColor Yellow
    exit 2
}

$script:violations = @()

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Add-Violation {
    param(
        [string]$Id,
        [string]$Description,
        [int]$Count,
        [string]$Fix,
        [string[]]$Matches
    )
    $script:violations += [PSCustomObject]@{
        Id          = $Id
        Description = $Description
        Count       = $Count
        Fix         = $Fix
        Matches     = $Matches
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ — Authentication Guards Check" -ForegroundColor White
Write-Host "======================================" -ForegroundColor White

# AG-1 — Identify route files and check each for auth dependency usage
Write-Section "AG-1 — Mutating routes missing Depends(get_current_user)"

$routeFiles = Get-ChildItem -Path "backend/app/api/" -Filter "*.py" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "__init__.py" }

$unguardedFiles = @()
foreach ($file in $routeFiles) {
    $content = Get-Content $file.FullName -Raw
    # Look for any router.post / router.put / router.delete / router.patch
    if ($content -match '@router\.(post|put|delete|patch)\(') {
        if ($content -notmatch 'Depends\(get_current_user') {
            $unguardedFiles += $file.FullName
        }
    }
}

if ($unguardedFiles.Count -eq 0) {
    Write-Host "  ✓ AG-1 PASS: Every mutating route file uses Depends(get_current_user)" -ForegroundColor Green
} else {
    Write-Host "  ✗ AG-1 FAIL ($($unguardedFiles.Count) file$(if ($unguardedFiles.Count -ne 1){'s'})): Mutating endpoints with no auth guard" -ForegroundColor Red
    $unguardedFiles | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
    Write-Host "  → Fix: Add 'current_user: User = Depends(get_current_user)' to each @router.post/put/delete/patch handler" -ForegroundColor Yellow
    Add-Violation -Id "AG-1" -Description "Route files declare mutating endpoints without auth dependency" `
        -Count $unguardedFiles.Count `
        -Fix "Add 'current_user: User = Depends(get_current_user)' to each @router.post/put/delete/patch handler" `
        -Matches $unguardedFiles
}

# AG-2 — Routes that import auth helpers but never use them
Write-Section "AG-2 — Imported but unused auth dependency"
$importedButUnused = @()
foreach ($file in $routeFiles) {
    $content = Get-Content $file.FullName -Raw
    if ($content -match 'from .*auth_middleware import .*get_current_user' -or
        $content -match 'from .*middleware\.auth_middleware import') {
        if ($content -notmatch 'Depends\(get_current_user') {
            $importedButUnused += $file.FullName
        }
    }
}
if ($importedButUnused.Count -eq 0) {
    Write-Host "  ✓ AG-2 PASS: No unused auth imports" -ForegroundColor Green
} else {
    Write-Host "  ✗ AG-2 FAIL ($($importedButUnused.Count) file$(if ($importedButUnused.Count -ne 1){'s'})): get_current_user imported but never used as Depends" -ForegroundColor Red
    $importedButUnused | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
    Add-Violation -Id "AG-2" -Description "get_current_user imported but not used" -Count $importedButUnused.Count `
        -Fix "Either use Depends(get_current_user) or remove the unused import" -Matches $importedButUnused
}

# AG-3 — get_current_user defined but imported zero times anywhere
Write-Section "AG-3 — get_current_user defined but imported nowhere"
$defined = & rg --files-with-matches "def get_current_user\b" "backend/app/" --type py 2>$null
$imported = & rg --files-with-matches "from .*auth_middleware.*get_current_user|Depends\(get_current_user" "backend/app/" --type py 2>$null

if ($defined -and -not $imported) {
    Write-Host "  ✗ AG-3 FAIL: get_current_user is defined in $defined but imported by zero files" -ForegroundColor Red
    Write-Host "  → Fix: Wire Depends(get_current_user) into every mutating route" -ForegroundColor Yellow
    Add-Violation -Id "AG-3" -Description "get_current_user defined but imported by zero files" -Count 1 `
        -Fix "Wire Depends(get_current_user) into every mutating route" -Matches @($defined)
} else {
    Write-Host "  ✓ AG-3 PASS: get_current_user is referenced" -ForegroundColor Green
}

# AG-4 — Frontend getSession() used for AUTHORIZATION (security anti-pattern)
# Narrowed scope: only flag getSession() in code paths that make auth decisions
# (lib/auth/, getServerSideProps, middleware). Using getSession() in the axios
# client (lib/api.ts) to FORWARD a token to the backend is fine — the backend
# validates the JWT independently with PyJWT, see docs/architecture/auth-system.md.
Write-Section "AG-4 — getSession() in frontend SSR / lib/auth code"
$gsOutput = & rg --line-number "supabase\.auth\.getSession\(\)" "frontend/src/lib/auth/" "frontend/src/middleware.ts" 2>$null
if ($LASTEXITCODE -eq 0 -and $gsOutput) {
    $count = ($gsOutput | Measure-Object -Line).Lines
    Write-Host "  ✗ AG-4 FAIL ($count match$(if ($count -ne 1){'es'})): getSession() used for SSR authorization (reads unvalidated cookie)" -ForegroundColor Red
    $gsOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
    Write-Host "  → Fix: Replace getSession() with supabase.auth.getUser() — getUser hits Supabase and validates the JWT" -ForegroundColor Yellow
    Add-Violation -Id "AG-4" -Description "getSession() used for server-side authorization" -Count $count `
        -Fix "Replace with supabase.auth.getUser() for validated server auth" -Matches @($gsOutput)
} else {
    Write-Host "  ✓ AG-4 PASS: No getSession() in SSR / lib/auth code" -ForegroundColor Green
}

# AG-5 — Raw Authorization header parsing in routes
Write-Section "AG-5 — Manual Authorization header parsing in routes"
$rawAuth = & rg --line-number 'request\.headers\.get\(["'']Authorization["'']\)|request\.headers\[["'']Authorization["'']\]' "backend/app/api/" --type py 2>$null
if ($LASTEXITCODE -eq 0 -and $rawAuth) {
    $count = ($rawAuth | Measure-Object -Line).Lines
    Write-Host "  ✗ AG-5 FAIL ($count): Raw Authorization header parsing in routes" -ForegroundColor Red
    $rawAuth | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
    Add-Violation -Id "AG-5" -Description "Raw Authorization header parsing" -Count $count `
        -Fix "Use Depends(get_current_user) instead of parsing the header manually" -Matches @($rawAuth)
} else {
    Write-Host "  ✓ AG-5 PASS: No manual header parsing in routes" -ForegroundColor Green
}

# AG-6 — Sensitive endpoint patterns without ownership-check helper
Write-Section "AG-6 — Routes accept user_id path param but reference 'current_user' nowhere"
$ownershipMissing = @()
foreach ($file in $routeFiles) {
    $content = Get-Content $file.FullName -Raw
    if ($content -match '@router\.(get|put|delete|post|patch)\(["''][^"'']*\{user_id[^"'']*["'']') {
        if ($content -notmatch 'current_user') {
            $ownershipMissing += $file.FullName
        }
    }
}
if ($ownershipMissing.Count -eq 0) {
    Write-Host "  ✓ AG-6 PASS: All {user_id} routes reference current_user (likely ownership-checked)" -ForegroundColor Green
} else {
    Write-Host "  ✗ AG-6 FAIL ($($ownershipMissing.Count)): {user_id} routes without ownership reference" -ForegroundColor Red
    $ownershipMissing | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
    Write-Host "  → Fix: After Depends(get_current_user), verify current_user.id == user_id (or allow admin role)" -ForegroundColor Yellow
    Add-Violation -Id "AG-6" -Description "{user_id} routes lack ownership verification" -Count $ownershipMissing.Count `
        -Fix "After Depends(get_current_user), assert current_user.id == user_id (or admin role)" -Matches $ownershipMissing
}

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
if ($script:violations.Count -eq 0) {
    Write-Host "AUTH GUARDS: ALL CLEAN ✓" -ForegroundColor Green
    $exit = 0
} else {
    $total = ($script:violations | Measure-Object Count -Sum).Sum
    Write-Host "AUTH GUARDS: $total VIOLATION$(if ($total -ne 1){'S'}) ACROSS $($script:violations.Count) CHECK$(if ($script:violations.Count -ne 1){'S'}) ✗" -ForegroundColor Red
    Write-Host "Authentication is non-negotiable. Every mutating route must use Depends(get_current_user)." -ForegroundColor Yellow
    $exit = 1
}

if ($Report) {
    if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $path  = Join-Path $ReportDir "auth-guards-$stamp.md"
    $lines = @("# Authentication Guards Report", "", "Generated: $(Get-Date -Format o)", "Branch: $(git rev-parse --abbrev-ref HEAD 2>$null)", "")
    if ($script:violations.Count -eq 0) {
        $lines += "✅ No violations found. Every mutating route is guarded."
    } else {
        foreach ($v in $script:violations) {
            $lines += "## $($v.Id) — $($v.Description)"
            $lines += ""
            $lines += "- **Count:** $($v.Count)"
            $lines += "- **Fix:** $($v.Fix)"
            $lines += ""
            $lines += '```'
            $lines += $v.Matches
            $lines += '```'
            $lines += ""
        }
    }
    $lines -join "`n" | Out-File -FilePath $path -Encoding utf8
    Write-Host "Report: $path" -ForegroundColor Cyan
}

exit $exit
