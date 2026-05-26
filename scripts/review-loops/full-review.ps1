<#
.SYNOPSIS
    Run the entire ChessIQ grep-loop review suite.

.DESCRIPTION
    Sequentially executes all focused review checks and aggregates the
    results. Each child script writes its own per-check output and (when
    -Report is set) a markdown report into docs/review-reports/.

    Order is deliberate:
      1. check-file-sizes.ps1          (cheapest signal of design rot)
      2. check-duplicates.ps1          (catches duplicated abstractions)
      3. check-stockfish-violations.ps1
      4. check-route-violations.ps1
      5. check-db-access-violations.ps1
      6. check-auth-guards.ps1

    Exit codes:
      0  — all checks clean
      1  — at least one hard violation found

.PARAMETER Report
    Pass through to each child script; also writes a master summary report.

.PARAMETER ContinueOnFail
    Run every check even if an earlier one failed. Useful for surface-area
    audits. Default behaviour runs every check (we always want the full
    picture before refactoring).

.PARAMETER ReportDir
    Where reports are written. Defaults to docs/review-reports.

.EXAMPLE
    # Local quick run
    .\scripts\review-loops\full-review.ps1

    # CI / pre-merge run with reports
    .\scripts\review-loops\full-review.ps1 -Report
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

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$checks = @(
    @{ Name = "File Sizes";              Script = "check-file-sizes.ps1" }
    @{ Name = "Duplicates";              Script = "check-duplicates.ps1" }
    @{ Name = "Stockfish Violations";    Script = "check-stockfish-violations.ps1" }
    @{ Name = "Route Violations";        Script = "check-route-violations.ps1" }
    @{ Name = "DB Access Violations";    Script = "check-db-access-violations.ps1" }
    @{ Name = "Auth Guards";             Script = "check-auth-guards.ps1" }
)

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor White
Write-Host "║    ChessIQ — Full Grep-Loop Review Suite             ║" -ForegroundColor White
Write-Host "║    Branch: $((git rev-parse --abbrev-ref HEAD 2>$null).PadRight(42, ' '))║" -ForegroundColor White
Write-Host "║    Started: $((Get-Date -Format 'yyyy-MM-dd HH:mm:ss').PadRight(41, ' '))║" -ForegroundColor White
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor White

$results = @()

foreach ($check in $checks) {
    $path = Join-Path $scriptDir $check.Script
    Write-Host ""
    Write-Host "▶ Running: $($check.Name) ($($check.Script))" -ForegroundColor White
    Write-Host ("─" * 60) -ForegroundColor DarkGray

    if (-not (Test-Path $path)) {
        Write-Host "  ✗ Script not found: $path" -ForegroundColor Red
        $results += [PSCustomObject]@{
            Name   = $check.Name
            Script = $check.Script
            Status = "MISSING"
            Code   = -1
        }
        continue
    }

    try {
        if ($Report) {
            & $path -Report -ReportDir $ReportDir
        } else {
            & $path
        }
        $code = $LASTEXITCODE
    } catch {
        Write-Host "  ✗ Script threw: $_" -ForegroundColor Red
        $code = 1
    }

    $status = if ($code -eq 0) { "PASS" } else { "FAIL" }
    $results += [PSCustomObject]@{
        Name   = $check.Name
        Script = $check.Script
        Status = $status
        Code   = $code
    }
}

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor White
Write-Host "║                  SUITE SUMMARY                       ║" -ForegroundColor White
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor White

foreach ($r in $results) {
    $colour = switch ($r.Status) {
        "PASS"    { "Green" }
        "FAIL"    { "Red" }
        default   { "Yellow" }
    }
    $glyph = switch ($r.Status) {
        "PASS"    { "✓" }
        "FAIL"    { "✗" }
        default   { "?" }
    }
    Write-Host ("  {0}  {1,-28} {2}" -f $glyph, $r.Name, $r.Status) -ForegroundColor $colour
}

$failCount = ($results | Where-Object { $_.Status -ne "PASS" }).Count

Write-Host ""
if ($failCount -eq 0) {
    Write-Host "  All checks passed. PR is structurally clean." -ForegroundColor Green
    $exit = 0
} else {
    Write-Host "  $failCount check$(if ($failCount -ne 1){'s'}) failed. Address all hard violations before merging." -ForegroundColor Red
    $exit = 1
}

if ($Report) {
    if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $path  = Join-Path $ReportDir "full-review-$stamp.md"

    $lines = @(
        "# ChessIQ Full Review Report",
        "",
        "Generated: $(Get-Date -Format o)",
        "Branch: $(git rev-parse --abbrev-ref HEAD 2>$null)",
        "Commit: $(git rev-parse HEAD 2>$null)",
        "",
        "## Suite results",
        "",
        "| Check | Script | Status | Code |",
        "|-------|--------|--------|------|"
    )
    foreach ($r in $results) {
        $glyph = switch ($r.Status) { "PASS" { "✅" }; "FAIL" { "❌" }; default { "⚠️" } }
        $lines += "| $glyph $($r.Name) | ``$($r.Script)`` | $($r.Status) | $($r.Code) |"
    }
    $lines += ""
    $lines += "## Per-check reports"
    $lines += ""
    $lines += "Each check writes its own report into ``$ReportDir/``."
    $lines += ""
    $lines += "Open the most recent file matching each pattern for full detail:"
    $lines += "- ``file-sizes-*.md``"
    $lines += "- ``duplicates-*.md``"
    $lines += "- ``stockfish-violations-*.md``"
    $lines += "- ``route-violations-*.md``"
    $lines += "- ``db-access-*.md``"
    $lines += "- ``auth-guards-*.md``"

    $lines -join "`n" | Out-File -FilePath $path -Encoding utf8
    Write-Host ""
    Write-Host "  Master report: $path" -ForegroundColor Cyan
}

exit $exit
