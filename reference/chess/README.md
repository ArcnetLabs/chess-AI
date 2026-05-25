# Reference: Chess Logic

Source references for chess game representation, PGN parsing, FEN handling, and game notation.

## Populate This Directory

```bash
# python-chess — the chess logic library used in the backend
git clone --depth=1 https://github.com/niklasf/python-chess reference/chess/python-chess

# Key files to read:
#   python-chess/chess/__init__.py   — Board, Move, Piece classes
#   python-chess/chess/pgn.py        — PGN parsing and visitor pattern
#   python-chess/chess/engine.py     — UCI protocol and async engine wrapper
```

## Key Concepts

| Class/Function | Purpose | ChessIQ usage |
|---------------|---------|---------------|
| `chess.Board` | Represents a position | Position analysis input to Stockfish |
| `chess.pgn.read_game()` | Parse PGN string | Game import from Chess.com API |
| `chess.pgn.Game.mainline_moves()` | Iterate moves | Board walk for analysis |
| `chess.engine.AnalysisResult` | Stockfish output | CP score, best move, depth |

## ChessIQ PGN Pipeline

```python
# Pattern used in unified_analyzer.py
import chess
import chess.pgn
import io

def parse_pgn(pgn_string: str) -> chess.pgn.Game:
    return chess.pgn.read_game(io.StringIO(pgn_string))

def walk_positions(game: chess.pgn.Game):
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
        yield board.copy()  # snapshot for analysis
```

## How Agents Should Inspect This Reference

```bash
# Find Board, Move, Piece class definitions
rg "class Board|class Move|class Piece" reference/chess/python-chess/chess/ --type py

# Find PGN parsing API
rg "def read_game|class GameNode|mainline_moves" reference/chess/python-chess/chess/pgn.py

# Find FEN handling
rg "def.*fen|fen.*str" reference/chess/python-chess/chess/__init__.py --type py

# Check existing ChessIQ usage before adding chess logic
rg "import chess|from chess" backend/app/ --type py -l
```

## Reuse Safeguards — Never Duplicate These

| Pattern | Where it lives in ChessIQ | Never recreate in |
|---------|--------------------------|-------------------|
| PGN parsing | `unified_analyzer.py` via `chess.pgn.read_game()` | Routes, tasks, or other services |
| Board walk (position iteration) | `unified_analyzer.py` | Any other analyzer |
| FEN → board conversion | python-chess (`chess.Board(fen=...)`) | Custom reimplementations |
| ECO opening identification | PGN header parsing in analyzer | LLM (LLM does not reliably know ECO) |

```bash
# Before adding chess logic, verify no duplicate exists:
rg "def.*parse.*pgn\|def.*board.*from\|def.*fen" backend/app/ --type py
```

## Notes

- FEN strings are the canonical position format passed to Stockfish.
- PGN games from Chess.com include headers (Event, White, Black, Date, ECO).
- The ECO code in the PGN header identifies the opening — use this before asking the LLM.
- Never reimplement move legality checking — `chess.Board.legal_moves` handles this.
