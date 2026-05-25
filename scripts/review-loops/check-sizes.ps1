<#
.SYNOPSIS
    F-series file-size guard for ChessIQ.
    Flags oversized files that signal missing abstractions or mixed responsibilities.

    Thresholds:
      Python service/route files  > 300 lines  → must split
      Python files (other)        > 400 lines  → warning
      TypeScript React components > 200 lines  → must split
      TypeScript lib files        > 250 lines  → warning
      TypeScript pages            > 150 lines  → warning (pages should be thin)

.OUTPUTS
    Coloured pass/warn/fail lines. Exit code 0 = clean, 1 = violations found.

.EXAMPLE
    .\scripts\review-loops\check-sizes.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:violations = 0
$script:warnings = 0

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Check-FileSizes {
    param(
        [string]$id,
        [string]$description,
        [string]$path,
        [string]$pattern,
        [int]$hardLimit,
        [int]$warnLimit,
        [string]$fix
    )

    if (-not (Test-Path $path)) {
        Write-Host "  ? $id SKIP: path '$path' not found" -ForegroundColor DarkYellow
        return
    }

    $files = Get-ChildItem -Path $path -Recurse -Filter $pattern -File -ErrorAction SilentlyContinue
    $hardFails = @()
    $warnFails = @()

    foreach ($f in $files) {
        $lineCount = (Get-Content $f.FullName | Measure-Object -Line).Lines
        if ($lineCount -gt $hardLimit) {
            $hardFails += [PSCustomObject]@{ Path = $f.FullName.Replace((Get-Location).Path + '\', ''); Lines = $lineCount }
        } elseif ($lineCount -gt $warnLimit) {
            $warnFails += [PSCustomObject]@{ Path = $f.FullName.Replace((Get-Location).Path + '\', ''); Lines = $lineCount }
        }
    }

    if ($hardFails.Count -gt 0) {
        Write-Host "  ✗ $id FAIL ($($hardFails.Count) file$(if ($hardFails.Count -ne 1){'s'}) > $hardLimit lines): $description" -ForegroundColor Red
        $hardFails | ForEach-Object { Write-Host "    $($_.Lines) lines  $($_.Path)" -ForegroundColor DarkRed }
        Write-Host "  → Fix: $fix" -ForegroundColor Yellow
        $script:violations += $hardFails.Count
    }

    if ($warnFails.Count -gt 0) {
        Write-Host "  ⚠ $id WARN ($($warnFails.Count) file$(if ($warnFails.Count -ne 1){'s'}) > $warnLimit lines): $description" -ForegroundColor Yellow
        $warnFails | ForEach-Object { Write-Host "    $($_.Lines) lines  $($_.Path)" -ForegroundColor DarkYellow }
        $script:warnings += $warnFails.Count
    }

    if ($hardFails.Count -eq 0 -and $warnFails.Count -eq 0) {
        Write-Host "  ✓ $id PASS: $description (max $(($files | ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines } | Measure-Object -Maximum).Maximum) lines)" -ForegroundColor Green
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ File-Size Review — F-Series" -ForegroundColor White
Write-Host "=====================================" -ForegroundColor White

Write-Section "F1 — Python service files"
Check-FileSizes `
    -id "F1" `
    -description "Python service files > 300 lines (single responsibility violation)" `
    -path "backend/app/services" `
    -pattern "*.py" `
    -hardLimit 300 `
    -warnLimit 200 `
    -fix "Split into focused modules: chess_service.py → game_parser.py + position_evaluator.py etc."

Write-Section "F2 — FastAPI route files"
Check-FileSizes `
    -id "F2" `
    -description "FastAPI route files > 250 lines (too many endpoints in one router)" `
    -path "backend/app/api" `
    -pattern "*.py" `
    -hardLimit 250 `
    -warnLimit 150 `
    -fix "Group related routes into sub-routers: analysis_routes.py, game_routes.py, user_routes.py"

Write-Section "F3 — React component files"
Check-FileSizes `
    -id "F3" `
    -description "React component (.tsx) files > 200 lines (too much logic in one component)" `
    -path "frontend/src/components" `
    -pattern "*.tsx" `
    -hardLimit 200 `
    -warnLimit 120 `
    -fix "Extract sub-components, custom hooks, and utility functions into separate files"

Write-Section "F4 — Next.js page files"
Check-FileSizes `
    -id "F4" `
    -description "Next.js page files > 150 lines (pages should be thin orchestrators)" `
    -path "frontend/src/pages" `
    -pattern "*.tsx" `
    -hardLimit 150 `
    -warnLimit 100 `
    -fix "Pages should only compose components and wire data — extract logic to hooks/components"

Write-Section "F5 — TypeScript lib files"
Check-FileSizes `
    -id "F5" `
    -description "TypeScript lib files > 250 lines (utility files growing too large)" `
    -path "frontend/src/lib" `
    -pattern "*.ts" `
    -hardLimit 250 `
    -warnLimit 150 `
    -fix "Split large lib files by domain: api.ts → api/chess.ts + api/user.ts + api/analysis.ts"

Write-Section "F6 — Python task files"
Check-FileSizes `
    -id "F6" `
    -description "Celery task files > 200 lines (tasks should be thin — logic in services)" `
    -path "backend/app/tasks" `
    -pattern "*.py" `
    -hardLimit 200 `
    -warnLimit 100 `
    -fix "Celery tasks should call service functions, not contain business logic directly"

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
if ($script:violations -eq 0 -and $script:warnings -eq 0) {
    Write-Host "F-SERIES: ALL CLEAN ✓" -ForegroundColor Green
    exit 0
} elseif ($script:violations -eq 0) {
    Write-Host "F-SERIES: PASSED WITH $($script:warnings) OVERSIZED FILE$(if ($script:warnings -ne 1){'S'}) ⚠" -ForegroundColor Yellow
    Write-Host "Warnings should be addressed before they cross the hard limit." -ForegroundColor DarkYellow
    exit 0
} else {
    Write-Host "F-SERIES: $($script:violations) OVERSIZED FILE$(if ($script:violations -ne 1){'S'}) EXCEEDING HARD LIMIT ✗" -ForegroundColor Red
    Write-Host "Split these files before merging to maintain single-responsibility boundaries." -ForegroundColor Yellow
    exit 1
}
