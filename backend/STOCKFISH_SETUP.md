# Stockfish Engine Setup Guide

## Overview

IQChess uses Stockfish for chess position analysis. This guide will help you set up Stockfish for development and production environments.

## Quick Setup (Windows Development)

### Step 1: Download Stockfish

1. Visit: https://stockfishchess.org/download/
2. Download **Stockfish 17.1 for Windows** (or latest version)
3. Extract the downloaded archive

### Step 2: Place Binary in Project

Copy the `stockfish.exe` file to:
```
backend/stockfish/stockfish.exe
```

The directory structure should look like:
```
chess-AI/
├── backend/
│   ├── stockfish/
│   │   └── stockfish.exe  ← Place here
│   ├── app/
│   └── requirements.txt
```

### Step 3: Verify Installation

Run the test script:
```bash
cd backend
python tests/test_stockfish_engine.py
```

You should see:
```
✓ Engine initialized at: E:\chess\chess-AI\backend\stockfish\stockfish.exe
✓ Analyzing starting position...
✓ Evaluation: 20 centipawns
✓ Best move: e2e4
SUCCESS: Stockfish engine is working correctly!
```

## Linux/Mac Setup

### Option 1: Package Manager

**Ubuntu/Debian:**
```bash
sudo apt-get install stockfish
```

**macOS (Homebrew):**
```bash
brew install stockfish
```

### Option 2: Manual Installation

1. Download from: https://stockfishchess.org/download/
2. Extract and place in `backend/stockfish/stockfish`
3. Make executable: `chmod +x backend/stockfish/stockfish`

## Docker/Production

The Dockerfile automatically downloads and configures Stockfish during the build process. No manual setup required.

The engine is downloaded from the official Stockfish GitHub releases and placed in `/app/stockfish/stockfish`.

## Configuration

### Environment Variables

You can customize Stockfish behavior via environment variables in `.env`:

```env
# Stockfish Configuration
STOCKFISH_PATH=                    # Auto-detect if empty
STOCKFISH_DEPTH=15                 # Search depth (10-20 recommended)
STOCKFISH_TIME=1.0                 # Time per move in seconds
STOCKFISH_THREADS=2                # Number of CPU threads
STOCKFISH_HASH=256                 # Hash table size in MB
```

### Auto-Detection

If `STOCKFISH_PATH` is not set, the engine will automatically search for Stockfish in:

**Windows:**
- `backend/stockfish/stockfish.exe`
- `C:/Program Files/Stockfish/stockfish.exe`
- `C:/Stockfish/stockfish.exe`

**Linux:**
- `backend/stockfish/stockfish`
- `/usr/games/stockfish`
- `/usr/local/bin/stockfish`
- `/usr/bin/stockfish`

**macOS:**
- `backend/stockfish/stockfish`
- `/usr/local/bin/stockfish`
- `/opt/homebrew/bin/stockfish`

## Testing

### Run All Engine Tests

```bash
cd backend
pytest tests/test_stockfish_engine.py -v
```

### Quick Verification

```bash
python tests/test_stockfish_engine.py
```

### Test Specific Functionality

```python
import asyncio
from app.services.engine.stockfish_engine import StockfishEngine
import chess

async def test():
    async with StockfishEngine() as engine:
        board = chess.Board()
        result = await engine.evaluate_position(board)
        print(f"Evaluation: {result}")

asyncio.run(test())
```

## Troubleshooting

### Error: "Stockfish binary not found"

**Solution:**
1. Verify `stockfish.exe` is in `backend/stockfish/`
2. Check file permissions (should be executable)
3. Try setting `STOCKFISH_PATH` explicitly in `.env`

### Error: "Engine terminated unexpectedly"

**Solution:**
1. Ensure you downloaded the correct version for your CPU architecture
2. Try the non-AVX2 version if you have an older CPU
3. Check antivirus isn't blocking the executable

### Error: "Permission denied"

**Linux/Mac:**
```bash
chmod +x backend/stockfish/stockfish
```

### Performance Issues

If analysis is slow:
1. Increase `STOCKFISH_THREADS` (max = CPU cores)
2. Increase `STOCKFISH_HASH` (more RAM = faster)
3. Reduce `STOCKFISH_DEPTH` for faster but less accurate analysis

## Advanced Usage

### Custom Engine Configuration

```python
from app.services.engine.stockfish_engine import StockfishEngine

engine = StockfishEngine(
    depth=20,           # Deeper search
    threads=4,          # More CPU cores
    hash_size=1024,     # 1GB hash table
    time_limit=2.0      # 2 seconds per move
)
```

### Analyzing Specific Positions

```python
import chess
from app.services.engine.stockfish_engine import StockfishEngine

async def analyze_position():
    async with StockfishEngine() as engine:
        # Set up position from FEN
        board = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
        
        result = await engine.evaluate_position(board)
        print(f"Evaluation: {result['evaluation_cp']} centipawns")
        print(f"Best move: {result['best_move']}")
```

## Version Information

- **Recommended:** Stockfish 17.1 or later
- **Minimum:** Stockfish 15.0
- **Python wrapper:** python-chess 1.999+

## Resources

- Official Website: https://stockfishchess.org/
- GitHub: https://github.com/official-stockfish/Stockfish
- Documentation: https://github.com/official-stockfish/Stockfish/wiki
- python-chess docs: https://python-chess.readthedocs.io/
