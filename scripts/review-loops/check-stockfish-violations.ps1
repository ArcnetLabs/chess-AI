<#
.SYNOPSIS
    Detect Stockfish instantiation outside the engine pool.

.DESCRIPTION
    Enforces invariant SF-1: only backend/app/services/engine/engine_pool.py
    may construct StockfishEngine / chess.engine.SimpleEngine / popen_uci.

    All other Stockfish access must go through the pool's acquire/release
    or analyze() API. Route handlers, Celery tasks, and other services
    must never instantiate engines directly.

.PARAMETER Report
    If set, writes a markdown report to docs/review-reports/.

.OUTPUTS
    Coloured pass/fail lines. Exit code 0 = clean, 1 = violations found.

.EXAMPLE
    .\scripts\review-loops\check-stockfish-violations.ps1
    .\scripts\review-loops\check-stockfish-violations.ps1 -Report
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

# ── Helpers ────────────────────────────────────────────────────────────────────

$script:violations = @()

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Run-Check {
    param(
        [string]$Id,
        [string]$Description,
        [string[]]$RgArgs,
        [string]$Fix,
        [int]$AllowedCount = 0
    )

    $output = & rg --line-number @RgArgs 2>$null
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        if ($count -le $AllowedCount) {
            Write-Host "  ✓ $Id PASS: $Description ($count match within allowance $AllowedCount)" -ForegroundColor Green
            return
        }
        Write-Host "  ✗ $Id FAIL ($count match$(if ($count -ne 1){'es'})): $Description" -ForegroundColor Red
        $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
        Write-Host "  → Fix: $Fix" -ForegroundColor Yellow
        $script:violations += [PSCustomObject]@{
            Id          = $Id
            Description = $Description
            Count       = $count
            Fix         = $Fix
            Matches     = @($output)
        }
    } elseif ($exitCode -eq 1) {
        Write-Host "  ✓ $Id PASS: $Description" -ForegroundColor Green
    } else {
        Write-Host "  ? $Id SKIP: rg error or path missing (exit $exitCode)" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ — Stockfish Violations Check" -ForegroundColor White
Write-Host "=====================================" -ForegroundColor White

Write-Section "SF-1 — chess.engine direct construction in routes / tasks"
Run-Check `
    -Id "SF-1" `
    -Description "chess.engine.SimpleEngine / popen_uci / chess.engine. in routes or tasks" `
    -RgArgs @("SimpleEngine|popen_uci|chess\.engine\.SimpleEngine", "backend/app/api/", "backend/app/tasks/", "--type", "py") `
    -Fix "Use 'from app.services.engine.engine_pool import get_engine_pool' and call pool.analyze(board, depth=15)"

Write-Section "SF-2 — StockfishEngine() instantiation in routes"
Run-Check `
    -Id "SF-2" `
    -Description "StockfishEngine(...) instantiated in route handlers" `
    -RgArgs @("StockfishEngine\(", "backend/app/api/", "--type", "py") `
    -Fix "Route handlers must never construct engines. Receive the pool via Depends() and call pool.analyze()."

Write-Section "SF-3 — StockfishEngine() in services outside engine pool"
$violatingServices = @()
$serviceMatches = & rg --line-number "StockfishEngine\(" "backend/app/services/" --type py 2>$null
if ($LASTEXITCODE -eq 0 -and $serviceMatches) {
    foreach ($line in $serviceMatches) {
        if ($line -notmatch "engine/engine_pool\.py" -and $line -notmatch "engine/stockfish_engine\.py") {
            $violatingServices += $line
        }
    }
}
if ($violatingServices.Count -eq 0) {
    Write-Host "  ✓ SF-3 PASS: StockfishEngine only constructed in engine_pool.py and stockfish_engine.py" -ForegroundColor Green
} else {
    Write-Host "  ✗ SF-3 FAIL ($($violatingServices.Count) match$(if ($violatingServices.Count -ne 1){'es'})): StockfishEngine instantiated outside the engine module" -ForegroundColor Red
    $violatingServices | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
    Write-Host "  → Fix: Accept the engine pool via constructor injection in services" -ForegroundColor Yellow
    $script:violations += [PSCustomObject]@{
        Id          = "SF-3"
        Description = "StockfishEngine instantiated outside engine module"
        Count       = $violatingServices.Count
        Fix         = "Accept the engine pool via constructor injection in services"
        Matches     = @($violatingServices)
    }
}

Write-Section "SF-4 — Hardcoded stockfish path strings"
Run-Check `
    -Id "SF-4" `
    -Description "Hardcoded /usr/games/stockfish or similar absolute paths in source" `
    -RgArgs @("['\""]/usr/(games|bin)/stockfish['\""]", "backend/app/", "--type", "py") `
    -Fix "Use settings.STOCKFISH_PATH from app.core.config (env-driven)"

Write-Section "SF-5 — Stockfish-python package direct import"
Run-Check `
    -Id "SF-5" `
    -Description "from stockfish import Stockfish (the package — bypasses pool)" `
    -RgArgs @("^from stockfish import|^import stockfish\b", "backend/app/", "--type", "py") `
    -Fix "Use app.services.engine.engine_pool (which wraps python-chess.engine) instead"

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
$total = ($script:violations | Measure-Object Count -Sum).Sum
if (-not $total) { $total = 0 }

if ($script:violations.Count -eq 0) {
    Write-Host "STOCKFISH CHECK: ALL CLEAN ✓" -ForegroundColor Green
    $exit = 0
} else {
    Write-Host "STOCKFISH CHECK: $total VIOLATION$(if ($total -ne 1){'S'}) ACROSS $($script:violations.Count) CHECK$(if ($script:violations.Count -ne 1){'S'}) ✗" -ForegroundColor Red
    Write-Host "Stockfish must only be instantiated inside the engine pool." -ForegroundColor Yellow
    $exit = 1
}

if ($Report) {
    if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $path  = Join-Path $ReportDir "stockfish-violations-$stamp.md"
    $lines = @("# Stockfish Violations Report", "", "Generated: $(Get-Date -Format o)", "Branch: $(git rev-parse --abbrev-ref HEAD 2>$null)", "Total violations: $total", "")
    if ($script:violations.Count -eq 0) {
        $lines += "✅ No violations found."
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
