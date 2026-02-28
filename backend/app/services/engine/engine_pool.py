"""Global Stockfish engine pool for reusing engine instances."""

import asyncio
from typing import Optional, Dict
from loguru import logger
import threading

from .stockfish_engine import StockfishEngine, StockfishEngineError
from ...core.config import settings


class StockfishEnginePool:
    """
    Event-loop-aware pool for managing Stockfish engine instances.
    
    Maintains one engine per event loop to handle background tasks correctly.
    Each event loop gets its own engine instance to avoid event loop conflicts.
    """
    
    _instance: Optional['StockfishEnginePool'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize the engine pool."""
        self.engines: Dict[int, StockfishEngine] = {}  # event_loop_id -> engine
        self._initialization_locks: Dict[int, asyncio.Lock] = {}
        
    @classmethod
    def get_instance(cls) -> 'StockfishEnginePool':
        """Get or create the singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def get_engine(self) -> StockfishEngine:
        """
        Get an initialized Stockfish engine instance for the current event loop.
        
        Returns:
            Initialized StockfishEngine instance
            
        Raises:
            StockfishEngineError: If engine initialization fails
        """
        # Get current event loop ID
        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            # No running loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop_id = id(loop)
        
        # Create lock for this event loop if it doesn't exist
        if loop_id not in self._initialization_locks:
            self._initialization_locks[loop_id] = asyncio.Lock()
        
        async with self._initialization_locks[loop_id]:
            # Check if engine exists for this event loop
            if loop_id not in self.engines or not self.engines[loop_id].is_initialized():
                if loop_id in self.engines:
                    logger.info(f"Re-initializing Stockfish engine for event loop {loop_id}")
                else:
                    logger.info(f"Creating new Stockfish engine for event loop {loop_id}")
                
                # Create new engine for this event loop
                engine = StockfishEngine(
                    stockfish_path=settings.STOCKFISH_PATH or None,
                    depth=settings.STOCKFISH_DEPTH,
                    threads=settings.STOCKFISH_THREADS,
                    hash_size=settings.STOCKFISH_HASH,
                    time_limit=settings.STOCKFISH_TIME
                )
                
                # Initialize the engine
                await engine.initialize()
                self.engines[loop_id] = engine
                logger.info(f"✅ Stockfish engine ready for event loop {loop_id}")
            
            return self.engines[loop_id]
    
    async def close_all(self):
        """Close all engines in the pool."""
        logger.info(f"Closing {len(self.engines)} Stockfish engine(s) in pool")
        for loop_id, engine in list(self.engines.items()):
            try:
                if engine and engine.is_initialized():
                    await engine.close()
            except Exception as e:
                logger.warning(f"Error closing engine for loop {loop_id}: {e}")
        self.engines.clear()
        self._initialization_locks.clear()
    
    @classmethod
    async def shutdown(cls):
        """Shutdown the global engine pool."""
        if cls._instance:
            await cls._instance.close_all()
            cls._instance = None


# Global function to get engine from pool
async def get_pooled_engine() -> StockfishEngine:
    """
    Get a reusable Stockfish engine from the global pool.
    
    This avoids the expensive initialization overhead by reusing
    the same engine instance for each event loop.
    
    Returns:
        Initialized StockfishEngine instance
    """
    pool = StockfishEnginePool.get_instance()
    return await pool.get_engine()
