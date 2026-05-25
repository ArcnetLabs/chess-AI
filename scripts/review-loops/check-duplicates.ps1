<#
.SYNOPSIS
    B-series duplicate logic checks for ChessIQ.
    Detects repeated implementations of game-fetching, analysis, auth, and API patterns.

.OUTPUTS
    Coloured pass/fail lines. Exit code 0 = clean, 1 = duplicates found.

.EXAMPLE
    .\scripts\review-loops\check-duplicates.ps1
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
        [int]$threshold = 1,
        [string]$fix,
        [switch]$warn
    )

    $output = & rg @rgArgs 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and $output) {
        $count = ($output | Measure-Object -Line).Lines
        if ($count -gt $threshold) {
            if ($warn) {
                Write-Host "  ⚠ $id WARN ($count definitions > threshold $threshold): $description" -ForegroundColor Yellow
                $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
                Write-Host "  → Consider: $fix" -ForegroundColor DarkYellow
                $script:warnings++
            } else {
                Write-Host "  ✗ $id FAIL ($count definitions): $description" -ForegroundColor Red
                $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
                Write-Host "  → Fix: $fix" -ForegroundColor Yellow
                $script:violations++
            }
        } else {
            Write-Host "  ✓ $id PASS ($count definition$(if ($count -ne 1){'s'})): $description" -ForegroundColor Green
        }
    } elseif ($exitCode -eq 1) {
        Write-Host "  ✓ $id PASS (0 matches): $description" -ForegroundColor Green
    } else {
        Write-Host "  ? $id SKIP: rg error or path missing" -ForegroundColor DarkYellow
    }
}

# ── Checks ─────────────────────────────────────────────────────────────────────

Write-Host "ChessIQ Duplicate Logic Review — B-Series" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor White

Write-Section "B1 — Duplicate game-fetching logic"
Run-Check `
    -id "B1" `
    -description "Multiple fetch_game / get_game functions (should be one in chesscom_api.py)" `
    -rgArgs @("def (fetch|get)_game", "backend/app/", "--type", "py") `
    -threshold 1 `
    -fix "Consolidate into backend/app/services/chesscom_api.py — delete duplicates"

Write-Section "B2 — Analysis logic outside unified analyzer"
Run-Check `
    -id "B2" `
    -description "analyze_position or evaluate_position defined outside services/" `
    -rgArgs @("def (analyze|evaluate)_(position|move|game)", "backend/app/api/", "backend/app/tasks/", "--type", "py") `
    -threshold 0 `
    -fix "Move analysis logic to backend/app/services/unified_analyzer.py"

Write-Section "B3 — Multiple Stockfish depth constants"
Run-Check `
    -id "B3" `
    -description "Hardcoded depth= values (should use a single ANALYSIS_DEPTH constant)" `
    -rgArgs @("depth=\d+", "backend/app/", "--type", "py") `
    -threshold 2 `
    -warn `
    -fix "Define ANALYSIS_DEPTH in backend/app/core/config.py and reference it everywhere"

Write-Section "B4 — Duplicate user-session retrieval patterns"
Run-Check `
    -id "B4" `
    -description "Manual supabase.auth.getUser() calls in pages (should use withAuth HOC)" `
    -rgArgs @("supabase\.auth\.getUser\(\)", "frontend/src/pages/", "--type", "ts") `
    -threshold 0 `
    -fix "Use withAuth HOC from frontend/src/lib/auth/withAuth.ts for all protected pages"

Write-Section "B5 — Duplicate Supabase client instantiation"
Run-Check `
    -id "B5" `
    -description "createClient()/createBrowserClient() called outside lib/supabase/ (should use shared client)" `
    -rgArgs @("createBrowserClient|createServerClient", "frontend/src/pages/", "frontend/src/components/", "--type", "ts") `
    -threshold 0 `
    -fix "Import from frontend/src/lib/supabase/client.ts or server.ts — never instantiate inline"

Write-Section "B6 — Duplicate API route handlers"
Run-Check `
    -id "B6" `
    -description "Multiple route handlers for the same chess action (look for /analysis, /analyze)" `
    -rgArgs @("@router\.(get|post)\(['\"]/(analyze|analysis)", "backend/app/api/", "--type", "py") `
    -threshold 1 `
    -warn `
    -fix "Merge duplicate route handlers — one endpoint per action"

Write-Section "B7 — Multiple React Query hooks for same resource"
Run-Check `
    -id "B7" `
    -description "useQuery hooks with same key string defined in multiple files" `
    -rgArgs @("useQuery\(\s*[\[{]", "frontend/src/pages/", "frontend/src/components/", "--type", "tsx") `
    -threshold 3 `
    -warn `
    -fix "Centralise React Query hooks in frontend/src/hooks/ — one hook file per resource type"

Write-Section "B8 — Duplicate PGN parsing logic"
Run-Check `
    -id "B8" `
    -description "chess.pgn / PGN parsing called outside chess service layer" `
    -rgArgs @("chess\.pgn\|io\.StringIO.*pgn\|pgn\.read_game", "backend/app/api/", "backend/app/tasks/", "--type", "py") `
    -threshold 0 `
    -fix "Centralise PGN parsing in backend/app/services/chess_service.py"

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════════" -ForegroundColor White
if ($script:violations -eq 0 -and $script:warnings -eq 0) {
    Write-Host "B-SERIES: ALL CLEAN ✓" -ForegroundColor Green
    exit 0
} elseif ($script:violations -eq 0) {
    Write-Host "B-SERIES: PASSED WITH $($script:warnings) WARNING$(if ($script:warnings -ne 1){'S'}) ⚠" -ForegroundColor Yellow
    Write-Host "Review warnings before the staging → main release." -ForegroundColor DarkYellow
    exit 0
} else {
    Write-Host "B-SERIES: $($script:violations) VIOLATION$(if ($script:violations -ne 1){'S'}) + $($script:warnings) WARNING$(if ($script:warnings -ne 1){'S'}) ✗" -ForegroundColor Red
    exit 1
}
