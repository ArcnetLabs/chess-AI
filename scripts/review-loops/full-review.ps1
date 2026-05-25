<#
.SYNOPSIS
    ChessIQ Full Grep-Loop Review — runs all A–F check scripts and produces a consolidated report.

.DESCRIPTION
    Orchestrates all review scripts in order of severity:
      A — Architecture violations  (BLOCKING: must be 0)
      D — Security                 (BLOCKING: must be 0)
      B — Duplicate logic          (BLOCKING for FAIL; warnings OK for PR)
      E — Database access          (BLOCKING for FAIL; warnings OK for PR)
      C — Naming consistency       (Warnings only — non-blocking)
      F — File sizes               (BLOCKING for FAIL; warnings non-blocking)

    Exit codes:
      0 — all blocking checks passed (PR is safe to merge)
      1 — one or more blocking checks failed (do not merge)

.PARAMETER Quick
    Run only the A-series (architecture) and D-series (security) checks.
    Use before every commit. Full suite reserved for pre-merge.

.PARAMETER Series
    Run a single series by letter: A, B, C, D, E, or F.

.EXAMPLE
    # Full suite (pre-merge)
    .\scripts\review-loops\full-review.ps1

    # Quick check (pre-commit)
    .\scripts\review-loops\full-review.ps1 -Quick

    # Single series
    .\scripts\review-loops\full-review.ps1 -Series B
#>

param(
    [switch]$Quick,
    [ValidateSet("A","B","C","D","E","F","")]
    [string]$Series = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$startTime = Get-Date
$results = [ordered]@{}

function Run-Script {
    param([string]$label, [string]$script, [bool]$blocking)

    Write-Host "`n" -NoNewline
    Write-Host ("═" * 60) -ForegroundColor DarkGray
    Write-Host "  Running $label" -ForegroundColor White
    Write-Host ("═" * 60) -ForegroundColor DarkGray

    & "$root\$script"
    $exit = $LASTEXITCODE

    $results[$label] = [PSCustomObject]@{
        Script   = $script
        ExitCode = $exit
        Blocking = $blocking
        Status   = if ($exit -eq 0) { "✓ PASS" } else { if ($blocking) { "✗ FAIL (BLOCKING)" } else { "⚠ WARN" } }
    }
}

# ── Verify rg is available ──────────────────────────────────────────────────────

if (-not (Get-Command rg -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: ripgrep (rg) is not installed or not on PATH." -ForegroundColor Red
    Write-Host "Install: winget install BurntSushi.ripgrep.MSVC" -ForegroundColor Yellow
    exit 2
}

# ── Verify we are at repo root ──────────────────────────────────────────────────

if (-not (Test-Path "backend") -and -not (Test-Path "frontend")) {
    Write-Host "WARNING: Neither 'backend/' nor 'frontend/' found in current directory." -ForegroundColor Yellow
    Write-Host "Run this script from the repository root." -ForegroundColor Yellow
}

Write-Host "`nChessIQ Full Grep-Loop Review" -ForegroundColor Cyan
Write-Host "Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
if ($Quick)  { Write-Host "Mode: QUICK (A + D series only)" -ForegroundColor DarkGray }
elseif ($Series) { Write-Host "Mode: SINGLE SERIES ($Series)" -ForegroundColor DarkGray }
else         { Write-Host "Mode: FULL SUITE (A–F)" -ForegroundColor DarkGray }

# ── Run scripts ────────────────────────────────────────────────────────────────

if ($Quick) {
    Run-Script "A — Architecture"  "check-architecture.ps1"  $true
    Run-Script "D — Security"       "check-security.ps1"       $true
} elseif ($Series) {
    $map = @{
        "A" = @{ script = "check-architecture.ps1"; blocking = $true }
        "B" = @{ script = "check-duplicates.ps1";   blocking = $true }
        "C" = @{ script = "check-naming.ps1";        blocking = $false }
        "D" = @{ script = "check-security.ps1";      blocking = $true }
        "E" = @{ script = "check-db-access.ps1";     blocking = $true }
        "F" = @{ script = "check-sizes.ps1";          blocking = $true }
    }
    $entry = $map[$Series]
    Run-Script "$Series — $Series series" $entry.script $entry.blocking
} else {
    Run-Script "A — Architecture"  "check-architecture.ps1"  $true
    Run-Script "D — Security"       "check-security.ps1"       $true
    Run-Script "B — Duplicates"     "check-duplicates.ps1"     $true
    Run-Script "E — DB Access"      "check-db-access.ps1"      $true
    Run-Script "C — Naming"         "check-naming.ps1"         $false
    Run-Script "F — File Sizes"     "check-sizes.ps1"          $true
}

# ── Consolidated Report ─────────────────────────────────────────────────────────

$elapsed = [int]((Get-Date) - $startTime).TotalSeconds
$blockingFailed = $results.Values | Where-Object { $_.Blocking -and $_.ExitCode -ne 0 }
$warnOnly       = $results.Values | Where-Object { -not $_.Blocking -and $_.ExitCode -ne 0 }

Write-Host "`n"
Write-Host ("═" * 60) -ForegroundColor White
Write-Host "  REVIEW SUMMARY — ChessIQ Grep-Loop" -ForegroundColor White
Write-Host ("═" * 60) -ForegroundColor White
Write-Host ""

foreach ($label in $results.Keys) {
    $r = $results[$label]
    $color = if ($r.ExitCode -eq 0) { "Green" } elseif ($r.Blocking) { "Red" } else { "Yellow" }
    Write-Host "  $($r.Status.PadRight(25)) $label" -ForegroundColor $color
}

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray

if ($blockingFailed.Count -eq 0) {
    Write-Host "  RESULT: READY TO MERGE ✓" -ForegroundColor Green
    if ($warnOnly.Count -gt 0) {
        Write-Host "  ($($warnOnly.Count) non-blocking warning$(if ($warnOnly.Count -ne 1){'s'}) — address before next release)" -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  RESULT: BLOCKED — $($blockingFailed.Count) check$(if ($blockingFailed.Count -ne 1){'s'}) failed ✗" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Failing checks:" -ForegroundColor Red
    $blockingFailed | ForEach-Object { Write-Host "    • $($_.Script)" -ForegroundColor DarkRed }
    Write-Host ""
    Write-Host "  Fix all blocking violations, re-run this script, then open the PR." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Completed in $($elapsed)s — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ("═" * 60) -ForegroundColor White

exit $(if ($blockingFailed.Count -gt 0) { 1 } else { 0 })
