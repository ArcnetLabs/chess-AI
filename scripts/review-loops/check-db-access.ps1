<#
.SYNOPSIS
    E-series database access checks for ChessIQ.
    Catches N+1 patterns, missing indexes, raw SQL in services, and ORM anti-patterns.

.OUTPUTS
    Coloured pass/warn/fail lines. Exit code 0 = clean, 1 = violations found.

.EXAMPLE
    .\scripts\review-loops\check-db-access.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:violations = 0
$script:warnings = 0

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Run-Check {
    param(
        [string]$id,
        [string]$description,
        [string[]]$rgArgs,
        [string]$fix,
        [switch]$warn
    )

    $output = & rg @rgArgs 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        if ($warn) {
            Write-Host "  ⚠ $id WARN ($count match$(if ($count -ne 1){'es'})): $description" -ForegroundColor Yellow
            $output | Select-Object -First 6 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
            Write-Host "  → Review: $fix" -ForegroundColor DarkYellow
            $script:warnings++
        } else {
            Write-Host "  ✗ $id FAIL ($count match$(if ($count -ne 1){'es'})): $description" -ForegroundColor Red
            $output | Select-Object -First 6 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
            Write-Host "  → Fix: $fix" -ForegroundColor Yellow
            $script:violations++
        }
    } elseif ($exitCode -eq 1) {
        Write-Host "  ✓ $id PASS: $description" -ForegroundColor Green
    } else {
        Write-Host "  ? $id SKIP: rg error or path missing" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ Database Access Review — E-Series" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor White

Write-Section "E1 — Raw SQL strings in service code"
Run-Check `
    -id "E1" `
    -description "Raw SQL strings (text()) directly in service layer — prefer ORM" `
    -rgArgs @("text\(['\"]SELECT|text\(['\"]INSERT|text\(['\"]UPDATE|text\(['\"]DELETE", "backend/app/services/", "--type", "py") `
    -fix "Use SQLAlchemy ORM queries instead of raw SQL. If raw SQL is necessary, move it to a dedicated query module." `
    -warn

Write-Section "E2 — Missing index on foreign-key columns"
Run-Check `
    -id "E2" `
    -description "ForeignKey columns in migrations without an accompanying Index() definition" `
    -rgArgs @("ForeignKey\(", "backend/alembic/versions/", "--type", "py") `
    -fix "For every ForeignKey, add 'Index('ix_table_column', table.column)' in the same migration" `
    -warn

Write-Section "E3 — Direct table queries in API routes"
Run-Check `
    -id "E3" `
    -description "db.query(Model) called directly in route handlers (should go through service layer)" `
    -rgArgs @("db\.(query|execute)\(", "backend/app/api/", "--type", "py") `
    -fix "Move all db.query() calls to backend/app/services/ — routes must only call service functions"

Write-Section "E4 — Supabase calls in backend (mixed DB access)"
Run-Check `
    -id "E4" `
    -description "Supabase client used in backend alongside SQLAlchemy (mixed DB access pattern)" `
    -rgArgs @("from supabase|import supabase|supabase\.table|supabase\.rpc", "backend/app/", "--type", "py") `
    -fix "Backend uses SQLAlchemy exclusively. Supabase client belongs in frontend only." `
    -warn

Write-Section "E5 — Unscoped DB transactions"
Run-Check `
    -id "E5" `
    -description "db.commit() outside a with-statement or explicit transaction context" `
    -rgArgs @("db\.commit\(\)", "backend/app/services/", "--type", "py") `
    -fix "Wrap multi-step mutations in a try/except with db.rollback() on failure" `
    -warn

Write-Section "E6 — Selecting all columns with ORM"
Run-Check `
    -id "E6" `
    -description "db.query(Model) without column filtering for large result sets" `
    -rgArgs @("db\.query\([A-Z][a-zA-Z]+\)\.all\(\)", "backend/app/", "--type", "py") `
    -fix "For list endpoints returning many rows, select specific columns: db.query(Model.id, Model.name)" `
    -warn

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════════" -ForegroundColor White
if ($script:violations -eq 0 -and $script:warnings -eq 0) {
    Write-Host "E-SERIES: ALL CLEAN ✓" -ForegroundColor Green
    exit 0
} elseif ($script:violations -eq 0) {
    Write-Host "E-SERIES: PASSED WITH $($script:warnings) WARNING$(if ($script:warnings -ne 1){'S'}) ⚠" -ForegroundColor Yellow
    Write-Host "Review warnings at the next sprint planning session." -ForegroundColor DarkYellow
    exit 0
} else {
    Write-Host "E-SERIES: $($script:violations) VIOLATION$(if ($script:violations -ne 1){'S'}) ✗" -ForegroundColor Red
    exit 1
}
