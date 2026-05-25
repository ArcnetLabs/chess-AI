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

## Notes

- FEN strings are the canonical position format passed to Stockfish.
- PGN games from Chess.com include headers (Event, White, Black, Date, ECO).
- The ECO code in the PGN header identifies the opening — use this before asking the LLM.
