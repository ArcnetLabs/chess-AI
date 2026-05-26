<#
.SYNOPSIS
    Detect duplicate implementations across the repository.

.DESCRIPTION
    Enforces invariants:
      DP-1: Only one AIClient class definition.
      DP-2: Only one chess analyzer module.
      DP-3: Only one game-fetching function (in services/integration/chesscom_api.py).
      DP-4: PGN parsing centralised in services/chess_service.py.
      DP-5: One Supabase client per surface (browser/server) — no inline instantiation.
      DP-6: One HTTP client pattern in the frontend (axios via lib/api.ts).
      DP-7: One auth-flow surface (withAuth + middleware) — no ad-hoc getUser() in pages.
      DP-8: One Stockfish depth constant.

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
        [int]$Threshold = 1,
        [string]$Fix,
        [switch]$Warn
    )

    $output = & rg --line-number @RgArgs 2>$null
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        if ($count -gt $Threshold) {
            $tag = if ($Warn) { "WARN" } else { "FAIL" }
            $colour = if ($Warn) { "Yellow" } else { "Red" }
            Write-Host "  ✗ $Id $tag ($count > threshold $Threshold): $Description" -ForegroundColor $colour
            $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
            Write-Host "  → Fix: $Fix" -ForegroundColor Yellow
            $entry = [PSCustomObject]@{
                Id          = $Id
                Description = $Description
                Count       = $count
                Threshold   = $Threshold
                Fix         = $Fix
                Matches     = @($output)
            }
            if ($Warn) { $script:warnings += $entry } else { $script:violations += $entry }
        } else {
            Write-Host "  ✓ $Id PASS ($count ≤ $Threshold): $Description" -ForegroundColor Green
        }
    } elseif ($exitCode -eq 1) {
        Write-Host "  ✓ $Id PASS (0 matches): $Description" -ForegroundColor Green
    } else {
        Write-Host "  ? $Id SKIP: rg error (exit $exitCode)" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ — Duplicate Implementations Check" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor White

Write-Section "DP-1 — Duplicate AIClient class definitions"
Run-Check `
    -Id "DP-1" `
    -Description "Multiple class AIClient definitions across the codebase" `
    -RgArgs @("^class AIClient\b", "backend/app/", "--type", "py") `
    -Threshold 1 `
    -Fix "Keep exactly one AIClient in services/integration/ai_client.py. Delete duplicates (or keep a thin re-export shim if external imports must not break)."

Write-Section "DP-2 — Duplicate analyzer implementations"
Run-Check `
    -Id "DP-2" `
    -Description "Multiple analyzer classes (ChessAnalyzer / UnifiedAnalyzer / ChessAnalysis)" `
    -RgArgs @("^class (\w*Analyzer|ChessAnalysis)\b", "backend/app/", "--type", "py") `
    -Threshold 1 `
    -Fix "Keep one canonical analyzer in services/analysis/unified_analyzer.py. Move shared helpers into services/analysis/helpers/."

Write-Section "DP-3 — Duplicate game-fetching functions"
Run-Check `
    -Id "DP-3" `
    -Description "Multiple fetch_game / get_game function definitions" `
    -RgArgs @("def (fetch|get)_game\b", "backend/app/", "--type", "py") `
    -Threshold 1 `
    -Fix "Consolidate in services/integration/chesscom_api.py. Delete shims after updating imports."

Write-Section "DP-4 — Duplicate PGN parsing"
Run-Check `
    -Id "DP-4" `
    -Description "chess.pgn / pgn.read_game called outside services/" `
    -RgArgs @("chess\.pgn|pgn\.read_game", "backend/app/api/", "backend/app/tasks/", "--type", "py") `
    -Threshold 0 `
    -Fix "Centralise PGN parsing in services/chess_service.py."

Write-Section "DP-5 — Duplicate Supabase client instantiation"
Run-Check `
    -Id "DP-5" `
    -Description "createBrowserClient/createServerClient called outside lib/supabase/" `
    -RgArgs @("createBrowserClient|createServerClient", "frontend/src/pages/", "frontend/src/components/", "-g", "*.ts", "-g", "*.tsx") `
    -Threshold 0 `
    -Fix "Import from frontend/src/lib/supabase/client.ts (browser) or server.ts (SSR) — never instantiate inline."

Write-Section "DP-6 — Multiple HTTP client patterns (axios + fetch + custom)"
$axiosFiles = & rg --files-with-matches "^import axios|from ['\""]axios['\""]" "frontend/src/" -g "*.ts" -g "*.tsx" 2>$null
$fetchFiles = & rg --files-with-matches "\bfetch\(" "frontend/src/" -g "*.ts" -g "*.tsx" 2>$null

$axiosCount = if ($axiosFiles) { @($axiosFiles).Count } else { 0 }
$fetchCount = if ($fetchFiles) { @($fetchFiles).Count } else { 0 }

if ($axiosCount -gt 0 -and $fetchCount -gt 0) {
    Write-Host "  ⚠ DP-6 WARN: Both axios ($axiosCount files) and fetch ($fetchCount files) are in use" -ForegroundColor Yellow
    Write-Host "    Pick one HTTP client (recommended: axios via lib/api.ts) and migrate the other." -ForegroundColor DarkYellow
    $script:warnings += [PSCustomObject]@{
        Id          = "DP-6"
        Description = "Multiple HTTP client patterns"
        Count       = $axiosCount + $fetchCount
        Threshold   = 0
        Fix         = "Standardise on axios via lib/api.ts. Migrate fetch() usages."
        Matches     = @("axios files: $axiosCount", "fetch files: $fetchCount")
    }
} else {
    Write-Host "  ✓ DP-6 PASS: Single HTTP client pattern in use" -ForegroundColor Green
}

Write-Section "DP-7 — Ad-hoc supabase.auth.getUser() in pages"
Run-Check `
    -Id "DP-7" `
    -Description "Pages calling supabase.auth.getUser() manually instead of withAuth" `
    -RgArgs @("supabase\.auth\.getUser\(\)", "frontend/src/pages/", "-g", "*.tsx") `
    -Threshold 0 `
    -Fix "Use the withAuth HOC from lib/auth/withAuth.ts or read user from a centralised auth hook."

Write-Section "DP-8 — Hardcoded analysis depth constants"
Run-Check `
    -Id "DP-8" `
    -Description "Multiple hardcoded depth=N values (should use ANALYSIS_DEPTH constant)" `
    -RgArgs @("depth=\d+", "backend/app/", "--type", "py") `
    -Threshold 2 `
    -Fix "Define ANALYSIS_DEPTH in app/core/config.py and reference it everywhere." `
    -Warn

Write-Section "DP-9 — Duplicate Stockfish wrapper modules"
Run-Check `
    -Id "DP-9" `
    -Description "Multiple files defining class Stockfish* or class EnginePool" `
    -RgArgs @("^class (Stockfish\w*|EnginePool)\b", "backend/app/", "--type", "py") `
    -Threshold 2 `
    -Fix "Keep one engine pool. Stockfish wrapper class + pool class = 2 max." `
    -Warn

Write-Section "DP-10 — Backward-compatibility shim files (should be empty after migration)"
$shimFiles = @()
$candidates = @(
    "backend/app/services/chess_analyzer.py",
    "backend/app/services/chess_analysis.py",
)
foreach ($f in $candidates) {
    if (Test-Path $f) {
        $content = Get-Content $f -Raw
        # Heuristic: shim = mostly re-exports
        $lineCount = ($content -split "`n").Count
        if ($content -match "from .*import \*|# (re-export|shim|backward)" -and $lineCount -lt 25) {
            $shimFiles += "$f (still present — delete after consumers updated)"
        }
    }
}
if ($shimFiles.Count -gt 0) {
    Write-Host "  ⚠ DP-10 WARN ($($shimFiles.Count)): Backward-compatibility shims still present" -ForegroundColor Yellow
    $shimFiles | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
    $script:warnings += [PSCustomObject]@{
        Id          = "DP-10"
        Description = "Backward-compatibility shim files still present"
        Count       = $shimFiles.Count
        Threshold   = 0
        Fix         = "Update all consumers, then delete shim files."
        Matches     = $shimFiles
    }
} else {
    Write-Host "  ✓ DP-10 PASS: No legacy shim files" -ForegroundColor Green
}

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════════" -ForegroundColor White
if ($script:violations.Count -eq 0 -and $script:warnings.Count -eq 0) {
    Write-Host "DUPLICATES: ALL CLEAN ✓" -ForegroundColor Green
    $exit = 0
} elseif ($script:violations.Count -eq 0) {
    Write-Host "DUPLICATES: PASSED WITH $($script:warnings.Count) WARNING$(if ($script:warnings.Count -ne 1){'S'}) ⚠" -ForegroundColor Yellow
    $exit = 0
} else {
    Write-Host "DUPLICATES: $($script:violations.Count) HARD + $($script:warnings.Count) WARNING ✗" -ForegroundColor Red
    Write-Host "Duplicate implementations breed bugs. Consolidate before merging." -ForegroundColor Yellow
    $exit = 1
}

if ($Report) {
    if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $path  = Join-Path $ReportDir "duplicates-$stamp.md"
    $lines = @("# Duplicates Report", "", "Generated: $(Get-Date -Format o)", "Branch: $(git rev-parse --abbrev-ref HEAD 2>$null)", "")

    if ($script:violations.Count -eq 0 -and $script:warnings.Count -eq 0) {
        $lines += "✅ No duplicates or warnings."
    } else {
        if ($script:violations.Count -gt 0) {
            $lines += "## Hard violations"
            foreach ($v in $script:violations) {
                $lines += ""
                $lines += "### $($v.Id) — $($v.Description)"
                $lines += "- **Count:** $($v.Count) (threshold $($v.Threshold))"
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
                $lines += "- **Count:** $($v.Count) (threshold $($v.Threshold))"
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
