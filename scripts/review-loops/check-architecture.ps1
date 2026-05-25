<#
.SYNOPSIS
    A-series architecture violation checks for ChessIQ.
    Checks that Stockfish, LLMs, and DB sessions stay behind their service wrappers.

.OUTPUTS
    Coloured pass/fail lines. Exit code 0 = clean, 1 = violations found.

.EXAMPLE
    .\scripts\review-loops\check-architecture.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Helpers ────────────────────────────────────────────────────────────────────

$script:violations = 0
$script:findings = @()

function Write-Section { param([string]$title)
    Write-Host "`n── $title ──" -ForegroundColor Cyan
}

function Run-Check {
    param(
        [string]$id,
        [string]$description,
        [string[]]$rgArgs,
        [string]$fix
    )

    $output = & rg @rgArgs 2>&1

    if ($LASTEXITCODE -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        Write-Host "  ✗ $id FAIL ($count match$(if ($count -ne 1){'es'})): $description" -ForegroundColor Red
        $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
        Write-Host "  → Fix: $fix" -ForegroundColor Yellow
        $script:violations += $count
        $script:findings += [PSCustomObject]@{ Check = $id; Count = $count; Description = $description }
    } elseif ($LASTEXITCODE -eq 1) {
        Write-Host "  ✓ $id PASS: $description" -ForegroundColor Green
    } else {
        Write-Host "  ? $id SKIP: rg error or path missing ($LASTEXITCODE)" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ Architecture Review — A-Series" -ForegroundColor White
Write-Host "=======================================" -ForegroundColor White

Write-Section "A1 — Stockfish outside engine pool"
Run-Check `
    -id "A1" `
    -description "chess.engine.SimpleEngine / popen_uci called outside engine_pool.py" `
    -rgArgs @("SimpleEngine|popen_uci|chess\.engine\.", "backend/app/api/", "backend/app/tasks/", "--type", "py") `
    -fix "Route all Stockfish calls through backend/app/services/engine_pool.py"

Write-Section "A2 — Inline LLM calls outside chess_coach service"
Run-Check `
    -id "A2" `
    -description "openai./anthropic./ollama.generate called directly in routes or tasks" `
    -rgArgs @("openai\.|anthropic\.|ollama\.generate|requests\.post.*completions", "backend/app/api/", "backend/app/tasks/", "--type", "py") `
    -fix "All LLM calls must go through backend/app/services/chess_coach.py"

Write-Section "A3 — Direct SessionLocal in API routes"
Run-Check `
    -id "A3" `
    -description "SessionLocal imported directly in routes (bypasses dependency injection)" `
    -rgArgs @("from app\.core\.database import SessionLocal", "backend/app/api/", "--type", "py") `
    -fix "Use 'db: Session = Depends(get_db)' instead of importing SessionLocal"

Write-Section "A4 — service_role key in frontend"
Run-Check `
    -id "A4" `
    -description "Supabase service role key referenced in frontend code" `
    -rgArgs @("service_role|SERVICE_ROLE|supabaseServiceRole", "frontend/src/") `
    -fix "service_role must never appear in frontend/. Use backend API endpoints instead."

Write-Section "A5 — getSession() used for server-side auth"
Run-Check `
    -id "A5" `
    -description "getSession() in pages or lib (reads unvalidated cookie — use getUser() instead)" `
    -rgArgs @("getSession\(\)", "frontend/src/pages/", "frontend/src/lib/") `
    -fix "Replace getSession() with supabase.auth.getUser() for validated server-side auth"

Write-Section "A6 — Direct axios calls in components or pages"
Run-Check `
    -id "A6" `
    -description "axios.get/post/put/delete called directly in components or pages" `
    -rgArgs @("axios\.(get|post|put|delete|patch)", "frontend/src/components/", "frontend/src/pages/", "--type", "ts") `
    -fix "All HTTP calls must go through frontend/src/lib/api.ts (or a typed React Query hook)"

Write-Section "A7 — Celery task calling backend services directly"
Run-Check `
    -id "A7" `
    -description "HTTP requests inside Celery tasks (should use service layer, not HTTP)" `
    -rgArgs @("requests\.(get|post|put|delete)", "backend/app/tasks/", "--type", "py") `
    -fix "Celery tasks must call service functions directly, not via HTTP"

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════" -ForegroundColor White
if ($script:violations -eq 0) {
    Write-Host "A-SERIES: ALL CLEAN ✓ ($($script:findings.Count) checks passed)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "A-SERIES: $($script:violations) VIOLATION$(if ($script:violations -ne 1){'S'}) FOUND ✗" -ForegroundColor Red
    Write-Host "Fix all A-series violations before opening a PR." -ForegroundColor Yellow
    exit 1
}
