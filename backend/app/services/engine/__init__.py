"""Chess engine services — acquire engines via the pool, not direct construction."""

from .engine_pool import (
    StockfishEnginePool,
    check_engine_health,
    get_pooled_engine,
)
from .stockfish_engine import StockfishEngine, StockfishEngineError

__all__ = [
    "StockfishEngine",
    "StockfishEngineError",
    "StockfishEnginePool",
    "check_engine_health",
    "get_pooled_engine",
]
