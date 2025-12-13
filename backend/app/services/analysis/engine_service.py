"""Stockfish engine wrapper for chess position evaluation."""

import chess.engine
from typing import Optional, Tuple
from loguru import logger


class StockfishEngineService:
    """Service for managing Stockfish engine connections and evaluations."""
    
    def __init__(self, stockfish_path: str = "/usr/games/stockfish"):
        self.stockfish_path = stockfish_path
        self.engine = None
        self.transport = None
    
    async def initialize(self):
        """Initialize the Stockfish engine."""
        if self.engine is None:
            self.transport, self.engine = await chess.engine.popen_uci(self.stockfish_path)
            logger.info(f"Stockfish engine initialized at {self.stockfish_path}")
    
    async def close(self):
        """Close the engine connection."""
        if self.engine:
            await self.engine.quit()
            self.engine = None
            self.transport = None
            logger.info("Stockfish engine closed")
    
    async def evaluate_position(
        self, 
        board: chess.Board, 
        depth: int = 15, 
        time_limit: float = 1.0
    ) -> Tuple[Optional[float], Optional[str], Optional[int]]:
        """
        Evaluate a chess position.
        
        Args:
            board: Chess board position
            depth: Search depth
            time_limit: Time limit in seconds
        
        Returns:
            Tuple of (evaluation_cp, best_move_uci, mate_in)
        """
        if not self.engine:
            await self.initialize()
        
        try:
            info = await self.engine.analyse(
                board, 
                chess.engine.Limit(depth=depth, time=time_limit)
            )
            
            score = info.get("score")
            best_move = info.get("pv")[0] if info.get("pv") else None
            
            if score:
                mate = score.relative.mate()
                if mate is not None:
                    return None, best_move.uci() if best_move else None, mate
                else:
                    cp = score.relative.score()
                    return cp, best_move.uci() if best_move else None, None
            
            return None, None, None
            
        except Exception as e:
            logger.error(f"Error evaluating position: {e}")
            return None, None, None
