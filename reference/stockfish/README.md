# Reference: Stockfish Integration

Source references for the Stockfish chess engine — UCI protocol, async wrappers, and the ChessIQ engine pool.

## Populate This Directory

```bash
git clone --depth=1 https://github.com/niklasf/python-chess reference/stockfish/python-chess
# Key file: python-chess/chess/engine.py
```

## ChessIQ Engine Pool

The engine pool lives at `backend/app/services/engine/engine_pool.py`.

**Never** instantiate `SimpleEngine` or `UciProtocol` directly in routes or tasks. Always go through the pool.

```python
# Correct usage
from app.services.engine.engine_pool import get_engine_pool

pool = get_engine_pool()
result = await pool.analyze(board, depth=15)
```

## UCI Protocol Notes

Stockfish communicates over UCI (Universal Chess Interface):

```
→ position fen <fen>
→ go depth <n>
← info depth 20 seldepth 30 score cp 45 ...
← bestmove e2e4 ponder e7e5
```

The `score cp` value is centipawns (+100 = 1 pawn advantage for white, -100 = 1 pawn advantage for black).

## Evaluation Thresholds (ChessIQ standard)

| CP delta | Classification |
|----------|---------------|
| 0–20 | Best move / fine |
| 21–50 | Inaccuracy |
| 51–150 | Mistake |
| 151–300 | Blunder |
| >300 | Severe blunder |

These thresholds are used in `unified_analyzer.py`. Do not define them elsewhere.

## Stockfish Binary

- Binary not committed to git (`backend/stockfish/.gitkeep` marks the empty directory).
- On Linux servers: `apt install stockfish` or download from `stockfishchess.org`.
- Path configured via `STOCKFISH_PATH` env var (default: `/usr/games/stockfish`).
- On Windows local dev: download the Windows binary to `backend/stockfish/stockfish.exe`.

## Depth vs. Time Configuration

Configure via environment variables in `backend/.env`:

```bash
STOCKFISH_DEPTH=15        # Default analysis depth
STOCKFISH_TIME=1.0        # Default time limit per position (seconds)
```

Override per-request in service calls:
```python
result = await pool.analyze(board, depth=18, time_limit=2.0)  # for critical positions
```
