<#
.SYNOPSIS
    Detect database-access boundary violations.

.DESCRIPTION
    Enforces invariants:
      DB-1: Routes must inject sessions via Depends(get_db), not import SessionLocal.
      DB-2: Components / pages must not contain Supabase database queries (.from(...)).
      DB-3: Backend services should accept a session, not create one with SessionLocal().
      DB-4: Raw SQL in routes — should live in services or repositories.
      DB-5: Multiple ORM patterns in the same codebase (SQLAlchemy + supabase-py + raw).

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
$script:warnings = @()

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Run-Check {
    param(
        [string]$Id,
        [string]$Description,
        [string[]]$RgArgs,
        [string]$Fix,
        [switch]$Warn,
        [int]$AllowedCount = 0
    )

    $output = & rg --line-number @RgArgs 2>$null
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        if ($count -le $AllowedCount) {
            Write-Host "  ✓ $Id PASS: $Description ($count within allowance $AllowedCount)" -ForegroundColor Green
            return
        }
        $tag = if ($Warn) { "WARN" } else { "FAIL" }
        $colour = if ($Warn) { "Yellow" } else { "Red" }
        Write-Host "  ✗ $Id $tag ($count): $Description" -ForegroundColor $colour
        $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
        Write-Host "  → Fix: $Fix" -ForegroundColor Yellow
        $entry = [PSCustomObject]@{
            Id          = $Id
            Description = $Description
            Count       = $count
            Fix         = $Fix
            Matches     = @($output)
        }
        if ($Warn) { $script:warnings += $entry } else { $script:violations += $entry }
    } elseif ($exitCode -eq 1) {
        Write-Host "  ✓ $Id PASS: $Description" -ForegroundColor Green
    } else {
        Write-Host "  ? $Id SKIP: rg error (exit $exitCode)" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ — DB Access Violations Check" -ForegroundColor White
Write-Host "=====================================" -ForegroundColor White

Write-Section "DB-1 — SessionLocal imported in API routes"
Run-Check `
    -Id "DB-1" `
    -Description "SessionLocal imported in backend/app/api/" `
    -RgArgs @("from .*core\.database import .*SessionLocal", "backend/app/api/", "--type", "py") `
    -Fix "Use 'db: Session = Depends(get_db)' for routes. Use 'with background_db_session()' in long-running tasks."

Write-Section "DB-2 — supabase.from() in components / pages"
Run-Check `
    -Id "DB-2" `
    -Description "supabase.from(...) calls in frontend components or pages" `
    -RgArgs @("supabase\.from\(", "frontend/src/components/", "frontend/src/pages/", "-g", "*.ts", "-g", "*.tsx") `
    -Fix "Wrap Supabase reads in /lib/supabase/queries/ helpers or hit backend API endpoints instead."

Write-Section "DB-3 — SessionLocal() invoked outside the engine/database modules"
$dbDirectInstantiation = & rg --line-number "SessionLocal\(\)" "backend/app/" --type py 2>$null
if ($LASTEXITCODE -eq 0 -and $dbDirectInstantiation) {
    $filtered = @($dbDirectInstantiation | Where-Object { $_ -notmatch "core/database\.py" -and $_ -notmatch "alembic" })
    if ($filtered.Count -gt 0) {
        $count = $filtered.Count
        Write-Host "  ⚠ DB-3 WARN ($count): SessionLocal() invoked outside core/database.py" -ForegroundColor Yellow
        $filtered | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
        Write-Host "  → Fix: Inject sessions; if a background context truly needs its own session, expose 'background_db_session()' from core/database.py" -ForegroundColor Yellow
        $script:warnings += [PSCustomObject]@{
            Id          = "DB-3"
            Description = "SessionLocal() outside core/database.py"
            Count       = $count
            Fix         = "Inject sessions or use a 'background_db_session()' helper"
            Matches     = $filtered
        }
    } else {
        Write-Host "  ✓ DB-3 PASS: SessionLocal() only used inside core/database.py" -ForegroundColor Green
    }
} else {
    Write-Host "  ✓ DB-3 PASS: SessionLocal() only used inside core/database.py" -ForegroundColor Green
}

Write-Section "DB-4 — Raw SQL via db.execute(text(...)) in routes"
Run-Check `
    -Id "DB-4" `
    -Description "Raw SQL inside route handlers" `
    -RgArgs @("db\.execute\(text\(|session\.execute\(text\(", "backend/app/api/", "--type", "py") `
    -Fix "Move raw SQL into a service / repository module. Routes should call db_service.fetch_games(...)." `
    -Warn

Write-Section "DB-5 — Mixed ORM patterns (SQLAlchemy + supabase-py) in same module"
$sqlAlchemyFiles = & rg --files-with-matches "from sqlalchemy" "backend/app/" --type py 2>$null
$supabasePyFiles = & rg --files-with-matches "from supabase import" "backend/app/" --type py 2>$null
if ($sqlAlchemyFiles -and $supabasePyFiles) {
    $overlap = @($sqlAlchemyFiles | Where-Object { $supabasePyFiles -contains $_ })
    if ($overlap.Count -gt 0) {
        Write-Host "  ⚠ DB-5 WARN ($($overlap.Count)): Files mixing SQLAlchemy + supabase-py" -ForegroundColor Yellow
        $overlap | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
        Write-Host "  → Fix: Pick one persistence boundary per module. Mixing leaks transaction semantics." -ForegroundColor Yellow
        $script:warnings += [PSCustomObject]@{
            Id          = "DB-5"
            Description = "Mixed SQLAlchemy + supabase-py"
            Count       = $overlap.Count
            Fix         = "Pick one persistence boundary per module"
            Matches     = $overlap
        }
    } else {
        Write-Host "  ✓ DB-5 PASS: No module mixes SQLAlchemy and supabase-py" -ForegroundColor Green
    }
} else {
    Write-Host "  ✓ DB-5 PASS: Only one ORM pattern detected" -ForegroundColor Green
}

Write-Section "DB-6 — Models imported by routes for ad-hoc queries"
Run-Check `
    -Id "DB-6" `
    -Description "Models imported in routes (acceptable if used for typing, but inspect for ad-hoc queries)" `
    -RgArgs @("from .*models\.\w+ import", "backend/app/api/", "--type", "py") `
    -Fix "Routes may reference response/request schemas but DB models should live in services / repositories." `
    -Warn `
    -AllowedCount 5

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
if ($script:violations.Count -eq 0 -and $script:warnings.Count -eq 0) {
    Write-Host "DB ACCESS: ALL CLEAN ✓" -ForegroundColor Green
    $exit = 0
} elseif ($script:violations.Count -eq 0) {
    Write-Host "DB ACCESS: $($script:warnings.Count) WARNING$(if ($script:warnings.Count -ne 1){'S'}) (no hard violations) ⚠" -ForegroundColor Yellow
    $exit = 0
} else {
    $total = ($script:violations | Measure-Object Count -Sum).Sum
    Write-Host "DB ACCESS: $total HARD VIOLATION$(if ($total -ne 1){'S'}) ACROSS $($script:violations.Count) CHECK$(if ($script:violations.Count -ne 1){'S'}) ✗" -ForegroundColor Red
    $exit = 1
}

if ($Report) {
    if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $path  = Join-Path $ReportDir "db-access-$stamp.md"
    $lines = @("# DB Access Violations Report", "", "Generated: $(Get-Date -Format o)", "Branch: $(git rev-parse --abbrev-ref HEAD 2>$null)", "")

    if ($script:violations.Count -eq 0 -and $script:warnings.Count -eq 0) {
        $lines += "✅ No violations or warnings."
    } else {
        if ($script:violations.Count -gt 0) {
            $lines += "## Hard violations"
            foreach ($v in $script:violations) {
                $lines += ""
                $lines += "### $($v.Id) — $($v.Description)"
                $lines += "- **Count:** $($v.Count)"
                $lines += "- **Fix:** $($v.Fix)"
                $lines += ""
                $lines += '```'
                $lines += $v.Matches
                $lines += '```'
            }
        }
        if ($script:warnings.Count -gt 0) {
            $lines += ""
            $lines += "## Warnings"
            foreach ($v in $script:warnings) {
                $lines += ""
                $lines += "### $($v.Id) — $($v.Description)"
                $lines += "- **Count:** $($v.Count)"
                $lines += "- **Fix:** $($v.Fix)"
                $lines += ""
                $lines += '```'
                $lines += $v.Matches
                $lines += '```'
            }
        }
    }

    $lines -join "`n" | Out-File -FilePath $path -Encoding utf8
    Write-Host "Report: $path" -ForegroundColor Cyan
}

exit $exit
