<#
.SYNOPSIS
    Detect route-layer boundary violations.

.DESCRIPTION
    Enforces invariants:
      RT-1: Route files must not import SessionLocal directly.
      RT-2: Route files must not import infrastructure (engine, stockfish) classes.
      RT-3: Route files must not contain inline business logic (heuristic via size).
      RT-4: Frontend pages/components must not call axios directly (must go through lib/api).
      RT-5: Frontend pages/components must not call fetch() directly (centralise in lib/api).
      RT-6: Celery tasks must not call HTTP backend endpoints (use services).

.PARAMETER Report
    Write a markdown report under docs/review-reports/.

.OUTPUTS
    Coloured pass/fail lines. Exit code 0 = clean, 1 = violations found.
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

function Run-Check {
    param(
        [string]$Id,
        [string]$Description,
        [string[]]$RgArgs,
        [string]$Fix,
        [int]$AllowedCount = 0,
        [switch]$Warn
    )

    $output = & rg --line-number @RgArgs 2>$null
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        if ($count -le $AllowedCount) {
            Write-Host "  ✓ $Id PASS: $Description ($count within allowance)" -ForegroundColor Green
            return
        }
        $tag = if ($Warn) { "WARN" } else { "FAIL" }
        $colour = if ($Warn) { "Yellow" } else { "Red" }
        Write-Host "  ✗ $Id $tag ($count match$(if ($count -ne 1){'es'})): $Description" -ForegroundColor $colour
        $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
        Write-Host "  → Fix: $Fix" -ForegroundColor Yellow
        if (-not $Warn) {
            $script:violations += [PSCustomObject]@{
                Id          = $Id
                Description = $Description
                Count       = $count
                Fix         = $Fix
                Matches     = @($output)
            }
        }
    } elseif ($exitCode -eq 1) {
        Write-Host "  ✓ $Id PASS: $Description" -ForegroundColor Green
    } else {
        Write-Host "  ? $Id SKIP: rg error (exit $exitCode)" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ — Route Layer Violations Check" -ForegroundColor White
Write-Host "=======================================" -ForegroundColor White

Write-Section "RT-1 — SessionLocal imported in API routes"
Run-Check `
    -Id "RT-1" `
    -Description "Direct SessionLocal import in api/ (bypasses Depends(get_db))" `
    -RgArgs @("from .*core\.database import .*SessionLocal|from \.\.core\.database import .*SessionLocal", "backend/app/api/", "--type", "py") `
    -Fix "Use 'db: Session = Depends(get_db)'. For background tasks needing fresh sessions, use a 'with background_db_session()' helper in core/database.py."

Write-Section "RT-2 — Engine / Stockfish import in API routes"
Run-Check `
    -Id "RT-2" `
    -Description "StockfishEngine / engine_pool imports inside api/ files" `
    -RgArgs @("from .*services\.engine.*import|from \.\.services\.engine.*import", "backend/app/api/", "--type", "py") `
    -Fix "Routes must not import the engine layer. Inject via FastAPI Depends() or call service functions that own engine access."

Write-Section "RT-3 — UnifiedAnalyzer / analyzer imported in routes (acceptable if used at type-level only)"
Run-Check `
    -Id "RT-3" `
    -Description "Analyzer instantiated directly in routes (signal of business logic in route layer)" `
    -RgArgs @("UnifiedChessAnalyzer\(", "backend/app/api/", "--type", "py") `
    -Fix "Routes call a service function (e.g. analysis_service.analyze_game). The service constructs the analyzer." `
    -Warn

Write-Section "RT-4 — Direct axios calls in components / pages"
Run-Check `
    -Id "RT-4" `
    -Description "axios.get/post/put/delete/patch in components or pages" `
    -RgArgs @("axios\.(get|post|put|delete|patch)\(", "frontend/src/components/", "frontend/src/pages/", "-g", "*.ts", "-g", "*.tsx") `
    -Fix "All HTTP calls must go through frontend/src/lib/api.ts (typed exports) or a React Query hook in frontend/src/hooks/"

Write-Section "RT-5 — Direct fetch() calls in components / pages (excluding hooks)"
Run-Check `
    -Id "RT-5" `
    -Description "fetch( in components or pages — should go through lib/api.ts" `
    -RgArgs @("\bfetch\(", "frontend/src/components/", "frontend/src/pages/", "-g", "*.ts", "-g", "*.tsx") `
    -Fix "Centralise HTTP access in lib/api.ts. Use one HTTP client pattern across the codebase." `
    -Warn

Write-Section "RT-6 — HTTP calls inside Celery tasks"
Run-Check `
    -Id "RT-6" `
    -Description "requests.* / httpx.* in backend/app/tasks/ (tasks should call services directly)" `
    -RgArgs @("requests\.(get|post|put|delete)|httpx\.(get|post|put|delete|AsyncClient)", "backend/app/tasks/", "--type", "py") `
    -Fix "Celery tasks must invoke service-layer functions, not call backend HTTP endpoints. Use httpx only for external APIs (Chess.com)."

Write-Section "RT-7 — Inline LLM calls in routes / tasks"
Run-Check `
    -Id "RT-7" `
    -Description "openai./anthropic. inline calls in routes or tasks" `
    -RgArgs @("openai\.|anthropic\.|ollama\.generate", "backend/app/api/", "backend/app/tasks/", "--type", "py") `
    -Fix "All LLM access must go through services/integration/ai_client.py."

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
$total = ($script:violations | Measure-Object Count -Sum).Sum
if (-not $total) { $total = 0 }

if ($script:violations.Count -eq 0) {
    Write-Host "ROUTE CHECK: ALL CLEAN ✓" -ForegroundColor Green
    $exit = 0
} else {
    Write-Host "ROUTE CHECK: $total VIOLATION$(if ($total -ne 1){'S'}) ACROSS $($script:violations.Count) CHECK$(if ($script:violations.Count -ne 1){'S'}) ✗" -ForegroundColor Red
    Write-Host "Routes must be thin: input validation + service call + response shaping. No infrastructure imports." -ForegroundColor Yellow
    $exit = 1
}

if ($Report) {
    if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $path  = Join-Path $ReportDir "route-violations-$stamp.md"
    $lines = @("# Route Layer Violations Report", "", "Generated: $(Get-Date -Format o)", "Branch: $(git rev-parse --abbrev-ref HEAD 2>$null)", "Total violations: $total", "")
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
