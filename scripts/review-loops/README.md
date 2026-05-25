# Review-Loop Scripts

Executable PowerShell scripts that run the ChessIQ grep-loop review suite automatically.
These scripts are the runnable counterpart to `skills/grep-loop-review.md` and `workflows/grep-review-process.md`.

---

## Requirements

- `ripgrep` (`rg`) must be on your PATH — install via `winget install BurntSushi.ripgrep.MSVC` or `choco install ripgrep`
- PowerShell 7+ (cross-platform; also works on PS 5.1 with minor colour differences)
- Run from the **repository root** (the directory containing `backend/` and `frontend/`)

---

## Script Reference

| Script | Purpose | Run time |
|--------|---------|----------|
| `full-review.ps1` | Runs all checks and prints a consolidated report | ~10 s |
| `check-architecture.ps1` | A-series: architecture violations (Stockfish, LLM, SessionLocal, service_role, getSession) | ~3 s |
| `check-duplicates.ps1` | B-series: duplicate service logic, repeated patterns | ~3 s |
| `check-security.ps1` | D-series: hardcoded secrets, unguarded routes, anon key leaks | ~3 s |
| `check-naming.ps1` | C-series: naming inconsistencies across files | ~2 s |
| `check-db-access.ps1` | E-series: N+1 patterns, missing indexes | ~2 s |
| `check-sizes.ps1` | File-size guard: flags oversized files that need splitting | ~2 s |

---

## Quickstart

```powershell
# From repo root — run the full suite
.\scripts\review-loops\full-review.ps1

# Run only architecture checks (fastest pre-PR gate)
.\scripts\review-loops\check-architecture.ps1

# Run only security checks
.\scripts\review-loops\check-security.ps1
```

Exit codes:
- `0` — all checks passed (zero real violations)
- `1` — one or more real violations found

---

## CI Integration

Add to your CI pipeline before running tests:

```yaml
- name: Architecture Review
  shell: pwsh
  run: .\scripts\review-loops\check-architecture.ps1
```

---

## Adding New Checks

1. Add the `rg` command to the appropriate `check-*.ps1` script.
2. Update `skills/grep-loop-review.md` with the same check (keeps docs and scripts in sync).
3. Update the quick-check block in `workflows/grep-review-workflow.md`.
4. Run `full-review.ps1` to confirm the new check works.

---

## Exemptions

When a finding is intentional (e.g., `engine_pool.py` directly calling `popen_uci`), add a trailing comment to the source line:

```python
engine = chess.engine.SimpleEngine.popen_uci(path)  # grep-exempt: engine pool definition
```

The review scripts do not filter exemptions automatically — triage them manually and note them in your PR description.
