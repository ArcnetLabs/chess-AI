<#
.SYNOPSIS
    Enforce per-file size limits across the repository.

.DESCRIPTION
    Each file class has a "warn" threshold and a "hard" limit. Hard limit
    violations fail the check. Warn-threshold violations log a warning.

    The thresholds reflect the architectural philosophy: large files
    almost always indicate missing abstractions or mixed responsibilities.

    Limits:
      FS-1  Python service files (backend/app/services/**.py)         warn 250, hard 300
      FS-2  Python route files (backend/app/api/**.py)                 warn 200, hard 250
      FS-3  Python task files (backend/app/tasks/**.py)                warn 200, hard 250
      FS-4  React components (frontend/src/components/**.tsx)          warn 200, hard 300
      FS-5  Next.js pages (frontend/src/pages/**.tsx)                  warn 100, hard 150
      FS-6  Frontend lib (frontend/src/lib/**.ts)                      warn 200, hard 250

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

$script:hardViolations = @()
$script:warnings = @()

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Check-Sizes {
    param(
        [string]$Id,
        [string]$Description,
        [string]$Path,
        [string]$Pattern,
        [int]$HardLimit,
        [int]$WarnLimit,
        [string]$Fix
    )

    Write-Section "$Id — $Description (warn $WarnLimit, hard $HardLimit)"

    if (-not (Test-Path $Path)) {
        Write-Host "  ? $Id SKIP: $Path does not exist" -ForegroundColor DarkYellow
        return
    }

    $files = Get-ChildItem -Path $Path -Recurse -Filter $Pattern -File -ErrorAction SilentlyContinue
    $hard = @()
    $warn = @()

    foreach ($file in $files) {
        $lineCount = (Get-Content $file.FullName -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
        if ($lineCount -gt $HardLimit) {
            $hard += [PSCustomObject]@{ Path = $file.FullName; Lines = $lineCount }
        } elseif ($lineCount -gt $WarnLimit) {
            $warn += [PSCustomObject]@{ Path = $file.FullName; Lines = $lineCount }
        }
    }

    if ($hard.Count -eq 0 -and $warn.Count -eq 0) {
        Write-Host "  ✓ $Id PASS: $($files.Count) files all within limits" -ForegroundColor Green
        return
    }

    foreach ($f in $hard) {
        Write-Host "  ✗ $Id FAIL HARD ($($f.Lines) lines > $HardLimit): $($f.Path)" -ForegroundColor Red
    }
    foreach ($w in $warn) {
        Write-Host "  ⚠ $Id WARN ($($w.Lines) lines > $WarnLimit): $($w.Path)" -ForegroundColor Yellow
    }
    if ($hard.Count -gt 0) {
        Write-Host "  → Fix: $Fix" -ForegroundColor Yellow
        $script:hardViolations += [PSCustomObject]@{
            Id          = $Id
            Description = $Description
            Fix         = $Fix
            Files       = $hard
        }
    }
    if ($warn.Count -gt 0) {
        $script:warnings += [PSCustomObject]@{
            Id          = $Id
            Description = $Description
            Fix         = $Fix
            Files       = $warn
        }
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ — File Size Limits Check" -ForegroundColor White
Write-Host "=================================" -ForegroundColor White

Check-Sizes -Id "FS-1" -Description "Python service files" `
    -Path "backend/app/services" -Pattern "*.py" `
    -HardLimit 300 -WarnLimit 250 `
    -Fix "Split into focused modules. Example: chess_service.py → game_parser.py + position_evaluator.py + score_aggregator.py."

Check-Sizes -Id "FS-2" -Description "Python route files (api/)" `
    -Path "backend/app/api" -Pattern "*.py" `
    -HardLimit 250 -WarnLimit 200 `
    -Fix "Routes should be thin. Move business logic into services. Split mega-route files by sub-resource."

Check-Sizes -Id "FS-3" -Description "Python Celery task files" `
    -Path "backend/app/tasks" -Pattern "*.py" `
    -HardLimit 250 -WarnLimit 200 `
    -Fix "Tasks should be thin orchestrators that call services. If a task file grows, the logic belongs in a service."

Check-Sizes -Id "FS-4" -Description "React components" `
    -Path "frontend/src/components" -Pattern "*.tsx" `
    -HardLimit 300 -WarnLimit 200 `
    -Fix "Extract sub-components. Move data fetching to hooks. Move complex render logic into smaller composed components."

Check-Sizes -Id "FS-5" -Description "Next.js pages" `
    -Path "frontend/src/pages" -Pattern "*.tsx" `
    -HardLimit 150 -WarnLimit 100 `
    -Fix "Pages compose components — they should not contain business logic. Move charts, cards, modals, and data hooks out of the page file."

Check-Sizes -Id "FS-6" -Description "Frontend lib files" `
    -Path "frontend/src/lib" -Pattern "*.ts" `
    -HardLimit 250 -WarnLimit 200 `
    -Fix "Split by domain. api.ts can become api/users.ts + api/games.ts + api/analysis.ts when it grows past 250."

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
if ($script:hardViolations.Count -eq 0 -and $script:warnings.Count -eq 0) {
    Write-Host "FILE SIZES: ALL CLEAN ✓" -ForegroundColor Green
    $exit = 0
} elseif ($script:hardViolations.Count -eq 0) {
    Write-Host "FILE SIZES: $($script:warnings.Count) WARNING CATEGORY/IES (no hard violations) ⚠" -ForegroundColor Yellow
    $exit = 0
} else {
    Write-Host "FILE SIZES: $($script:hardViolations.Count) HARD VIOLATION CATEGORY/IES, $($script:warnings.Count) WARNINGS ✗" -ForegroundColor Red
    Write-Host "Files over the hard limit must be split before this PR can merge." -ForegroundColor Yellow
    $exit = 1
}

if ($Report) {
    if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $path  = Join-Path $ReportDir "file-sizes-$stamp.md"
    $lines = @("# File Sizes Report", "", "Generated: $(Get-Date -Format o)", "")

    if ($script:hardViolations.Count -gt 0) {
        $lines += "## Hard violations"
        foreach ($v in $script:hardViolations) {
            $lines += ""
            $lines += "### $($v.Id) — $($v.Description)"
            $lines += "Fix: $($v.Fix)"
            $lines += ""
            $lines += "| File | Lines |"
            $lines += "|------|-------|"
            foreach ($f in $v.Files) {
                $lines += "| $($f.Path) | $($f.Lines) |"
            }
        }
    }

    if ($script:warnings.Count -gt 0) {
        $lines += ""
        $lines += "## Warnings"
        foreach ($v in $script:warnings) {
            $lines += ""
            $lines += "### $($v.Id) — $($v.Description)"
            $lines += ""
            $lines += "| File | Lines |"
            $lines += "|------|-------|"
            foreach ($f in $v.Files) {
                $lines += "| $($f.Path) | $($f.Lines) |"
            }
        }
    }

    if ($script:hardViolations.Count -eq 0 -and $script:warnings.Count -eq 0) {
        $lines += "✅ No violations or warnings."
    }

    $lines -join "`n" | Out-File -FilePath $path -Encoding utf8
    Write-Host "Report: $path" -ForegroundColor Cyan
}

exit $exit
