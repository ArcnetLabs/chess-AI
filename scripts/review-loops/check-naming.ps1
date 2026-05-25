<#
.SYNOPSIS
    C-series naming consistency checks for ChessIQ.
    Flags mixed naming conventions that create confusion across the codebase.

.OUTPUTS
    Coloured pass/warn lines. Exit code 0 = clean, 1 = violations found.

.EXAMPLE
    .\scripts\review-loops\check-naming.ps1
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
            $output | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
            if ($count -gt 5) { Write-Host "    ... ($($count - 5) more)" -ForegroundColor DarkYellow }
            Write-Host "  → Consider: $fix" -ForegroundColor DarkYellow
            $script:warnings++
        } else {
            Write-Host "  ✗ $id FAIL ($count match$(if ($count -ne 1){'es'})): $description" -ForegroundColor Red
            $output | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed }
            if ($count -gt 5) { Write-Host "    ... ($($count - 5) more)" -ForegroundColor DarkRed }
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

Write-Host "ChessIQ Naming Consistency Review — C-Series" -ForegroundColor White
Write-Host "=============================================" -ForegroundColor White

Write-Section "C1 — Mixed user-ID field names"
Run-Check `
    -id "C1" `
    -description "camelCase 'userId' or 'userID' used alongside snake_case 'user_id'" `
    -rgArgs @("userId\b|userID\b", "backend/app/", "--type", "py") `
    -fix "Python layer must use snake_case 'user_id' exclusively" `
    -warn

Write-Section "C2 — camelCase API route parameters"
Run-Check `
    -id "C2" `
    -description "camelCase path parameters in FastAPI routes (should be snake_case)" `
    -rgArgs @("@router\.(get|post|put|delete)\([^)]*[a-z][A-Z]", "backend/app/api/", "--type", "py") `
    -fix "Use snake_case for all route path parameters: /games/{game_id} not /games/{gameId}" `
    -warn

Write-Section "C3 — IInterface naming pattern in TypeScript"
Run-Check `
    -id "C3" `
    -description "'interface IFoo' pattern (use 'interface Foo' without I-prefix)" `
    -rgArgs @("interface I[A-Z][a-zA-Z]+", "frontend/src/", "--type", "ts") `
    -fix "Remove the I prefix: 'interface User' not 'interface IUser'" `
    -warn

Write-Section "C4 — Mixed TypeScript type vs interface"
Run-Check `
    -id "C4" `
    -description "Both 'type Foo =' and 'interface Foo' for similar object shapes in the same file" `
    -rgArgs @("^type [A-Z][a-zA-Z]+ =", "frontend/src/types/", "--type", "ts") `
    -fix "Prefer 'interface' for object shapes, 'type' for unions/intersections — be consistent" `
    -warn

Write-Section "C5 — Snake_case constants in TypeScript"
Run-Check `
    -id "C5" `
    -description "snake_case constants in TypeScript (should be SCREAMING_SNAKE or camelCase)" `
    -rgArgs @("const [a-z][a-z_]+[a-z] =", "frontend/src/lib/", "--type", "ts") `
    -fix "Constants: SCREAMING_SNAKE for module-level, camelCase for local" `
    -warn

Write-Section "C6 — Mixed endpoint path styles"
Run-Check `
    -id "C6" `
    -description "Endpoints using kebab-case segments (should be snake_case for FastAPI)" `
    -rgArgs @("@router\.(get|post|put|delete)\(['\"][^'\"]*-[^'\"]*['\"]\)", "backend/app/api/", "--type", "py") `
    -fix "Use snake_case for FastAPI paths: /chess_games not /chess-games" `
    -warn

Write-Section "C7 — Inconsistent component file naming"
Run-Check `
    -id "C7" `
    -description "Lowercase or kebab-case React component files (should be PascalCase.tsx)" `
    -rgArgs @("^[a-z].*\.tsx$", "frontend/src/components/", "--files") `
    -fix "Rename component files to PascalCase: ChessBoard.tsx not chess-board.tsx" `
    -warn

# ── Summary ────────────────────────────────────────────────────────────────────

Write-Host "`n═══════════════════════════════════════════" -ForegroundColor White
if ($script:violations -eq 0 -and $script:warnings -eq 0) {
    Write-Host "C-SERIES: ALL CLEAN ✓" -ForegroundColor Green
    exit 0
} elseif ($script:violations -eq 0) {
    Write-Host "C-SERIES: PASSED WITH $($script:warnings) WARNING$(if ($script:warnings -ne 1){'S'}) ⚠" -ForegroundColor Yellow
    Write-Host "Warnings are non-blocking for PRs but should be addressed before the next sprint." -ForegroundColor DarkYellow
    exit 0
} else {
    Write-Host "C-SERIES: $($script:violations) VIOLATION$(if ($script:violations -ne 1){'S'}) ✗" -ForegroundColor Red
    exit 1
}
