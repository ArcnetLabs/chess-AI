"""Unified Stockfish engine wrapper with error handling and cross-platform support."""

import os
import platform
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import chess
import chess.engine
from loguru import logger


class StockfishEngineError(Exception):
    """Custom exception for Stockfish engine errors."""
    pass


class StockfishEngine:
    """
    Unified Stockfish engine wrapper using python-chess UCI protocol.
    
    Features:
    - Cross-platform support (Windows, Linux, macOS)
    - Automatic path detection
    - Connection pooling and lifecycle management
    - Comprehensive error handling
    - Position evaluation and best move analysis
    """
    
    def __init__(
        self,
        stockfish_path: Optional[str] = None,
        depth: int = 15,
        threads: int = 2,
        hash_size: int = 256,
        time_limit: float = 1.0
    ):
        """
        Initialize Stockfish engine wrapper.
        
        Args:
            stockfish_path: Path to Stockfish binary. If None, auto-detect.
            depth: Search depth (default: 15)
            threads: Number of threads (default: 2)
            hash_size: Hash table size in MB (default: 256)
            time_limit: Time limit per move in seconds (default: 1.0)
        """
        self.stockfish_path = stockfish_path or self._detect_stockfish_path()
        self.depth = depth
        self.threads = threads
        self.hash_size = hash_size
        self.time_limit = time_limit
        
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.transport = None
        self._is_initialized = False
        
        logger.info(f"StockfishEngine configured with path: {self.stockfish_path}")
    
    def _detect_stockfish_path(self) -> str:
        """
        Auto-detect Stockfish binary path based on platform.
        
        Returns:
            Path to Stockfish binary
            
        Raises:
            StockfishEngineError: If Stockfish binary not found
        """
        system = platform.system()
        
        # Priority order for path detection
        search_paths = []
        
        if system == "Windows":
            search_paths = [
                # Local project directory (development)
                Path(__file__).parent.parent.parent.parent / "stockfish" / "stockfish.exe",
                Path(__file__).parent.parent.parent.parent / "stockfish" / "stockfish-windows-x86-64-avx2.exe",
                # Common Windows installation paths
                Path("C:/Program Files/Stockfish/stockfish.exe"),
                Path("C:/Stockfish/stockfish.exe"),
                # Current directory
                Path("stockfish.exe"),
            ]
        elif system == "Linux":
            search_paths = [
                # Local project directory
                Path(__file__).parent.parent.parent.parent / "stockfish" / "stockfish",
                # Common Linux paths
                Path("/usr/games/stockfish"),
                Path("/usr/local/bin/stockfish"),
                Path("/usr/bin/stockfish"),
                # Docker/container path
                Path("/app/stockfish/stockfish"),
            ]
        elif system == "Darwin":  # macOS
            search_paths = [
                Path(__file__).parent.parent.parent.parent / "stockfish" / "stockfish",
                Path("/usr/local/bin/stockfish"),
                Path("/opt/homebrew/bin/stockfish"),
            ]
        
        # Check each path
        for path in search_paths:
            if path.exists() and os.access(path, os.X_OK):
                logger.info(f"Found Stockfish at: {path}")
                return str(path)
        
        # If not found, raise detailed error
        error_msg = (
            f"Stockfish binary not found on {system}. Searched paths:\n" +
            "\n".join(f"  - {p}" for p in search_paths) +
            "\n\nPlease download Stockfish from https://stockfishchess.org/download/ " +
            "and place it in one of the above locations."
        )
        logger.error(error_msg)
        raise StockfishEngineError(error_msg)
    
    async def initialize(self) -> None:
        """
        Initialize the Stockfish engine connection.
        
        Raises:
            StockfishEngineError: If engine initialization fails
        """
        if self._is_initialized and self.engine:
            logger.debug("Engine already initialized")
            return
        
        try:
            logger.info(f"Initializing Stockfish engine from: {self.stockfish_path}")
            
            # Verify binary exists
            if not os.path.exists(self.stockfish_path):
                raise StockfishEngineError(
                    f"Stockfish binary not found at: {self.stockfish_path}"
                )
            
            # Start engine process
            try:
                self.transport, self.engine = await chess.engine.popen_uci(
                    self.stockfish_path
                )
            except PermissionError as e:
                raise StockfishEngineError(
                    f"Permission denied accessing Stockfish binary at {self.stockfish_path}. "
                    f"Make sure the file is executable."
                )
            except OSError as e:
                raise StockfishEngineError(
                    f"OS error starting Stockfish: {str(e)}. "
                    f"The binary may be corrupted or incompatible with your system."
                )
            
            # Configure engine options
            await self.engine.configure({
                "Threads": self.threads,
                "Hash": self.hash_size,
            })
            
            self._is_initialized = True
            logger.info(
                f"Stockfish engine initialized successfully "
                f"(depth={self.depth}, threads={self.threads}, hash={self.hash_size}MB)"
            )
            
        except FileNotFoundError as e:
            raise StockfishEngineError(
                f"Stockfish binary not found: {self.stockfish_path}. "
                f"Error: {str(e)}"
            )
        except chess.engine.EngineTerminatedError as e:
            raise StockfishEngineError(
                f"Stockfish engine terminated unexpectedly: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Stockfish initialization error details: {type(e).__name__}: {str(e)}")
            raise StockfishEngineError(
                f"Failed to initialize Stockfish engine: {type(e).__name__}: {str(e)}"
            )
    
    async def close(self) -> None:
        """Close the engine connection gracefully."""
        if self.engine:
            try:
                await self.engine.quit()
                logger.info("Stockfish engine closed successfully")
            except Exception as e:
                logger.warning(f"Error closing engine: {e}")
            finally:
                self.engine = None
                self.transport = None
                self._is_initialized = False
    
    async def evaluate_position(
        self,
        board: chess.Board,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a chess position.
        
        Args:
            board: Chess board position to evaluate
            depth: Search depth (uses instance default if None)
            time_limit: Time limit in seconds (uses instance default if None)
        
        Returns:
            Dictionary containing:
                - evaluation_cp: Evaluation in centipawns (from current player's perspective)
                - mate_in: Moves to mate (None if not mate)
                - best_move: Best move in UCI format
                - pv: Principal variation (list of moves)
                - is_mate: Boolean indicating if position is mate
        
        Raises:
            StockfishEngineError: If evaluation fails
        """
        if not self._is_initialized:
            await self.initialize()
        
        try:
            # Use provided values or defaults
            search_depth = depth or self.depth
            search_time = time_limit or self.time_limit
            
            # Analyze position
            info = await self.engine.analyse(
                board,
                chess.engine.Limit(depth=search_depth, time=search_time)
            )
            
            # Extract score
            score = info.get("score")
            if not score:
                raise StockfishEngineError("No score returned from engine")
            
            # Convert score to centipawns and mate info
            pov_score = score.relative
            mate_in = pov_score.mate()
            
            if mate_in is not None:
                # Mate score
                evaluation_cp = None
                is_mate = True
            else:
                # Centipawn score
                evaluation_cp = pov_score.score()
                is_mate = False
            
            # Extract best move and principal variation
            pv = info.get("pv", [])
            best_move = pv[0].uci() if pv else None
            pv_uci = [move.uci() for move in pv]
            
            result = {
                "evaluation_cp": evaluation_cp,
                "mate_in": mate_in,
                "best_move": best_move,
                "pv": pv_uci,
                "is_mate": is_mate,
                "depth": info.get("depth", search_depth),
            }
            
            logger.debug(
                f"Position evaluated: cp={evaluation_cp}, mate={mate_in}, "
                f"best_move={best_move}"
            )
            
            return result
            
        except chess.engine.EngineTerminatedError as e:
            self._is_initialized = False
            raise StockfishEngineError(f"Engine terminated during evaluation: {str(e)}")
        except Exception as e:
            raise StockfishEngineError(f"Position evaluation failed: {str(e)}")
    
    async def get_best_move(
        self,
        board: chess.Board,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None
    ) -> Optional[str]:
        """
        Get the best move for a position.
        
        Args:
            board: Chess board position
            depth: Search depth (uses instance default if None)
            time_limit: Time limit in seconds (uses instance default if None)
        
        Returns:
            Best move in UCI format, or None if no legal moves
        
        Raises:
            StockfishEngineError: If analysis fails
        """
        if not self._is_initialized:
            await self.initialize()
        
        try:
            search_depth = depth or self.depth
            search_time = time_limit or self.time_limit
            
            result = await self.engine.play(
                board,
                chess.engine.Limit(depth=search_depth, time=search_time)
            )
            
            return result.move.uci() if result.move else None
            
        except Exception as e:
            raise StockfishEngineError(f"Failed to get best move: {str(e)}")
    
    async def analyze_moves(
        self,
        board: chess.Board,
        moves: List[chess.Move],
        depth: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple moves from a position.
        
        Args:
            board: Starting chess board position
            moves: List of moves to analyze
            depth: Search depth (uses instance default if None)
        
        Returns:
            List of evaluation dictionaries for each move
        """
        if not self._is_initialized:
            await self.initialize()
        
        results = []
        search_depth = depth or self.depth
        
        for move in moves:
            # Make move on a copy of the board
            temp_board = board.copy()
            temp_board.push(move)
            
            # Evaluate resulting position
            eval_result = await self.evaluate_position(temp_board, depth=search_depth)
            eval_result["move"] = move.uci()
            results.append(eval_result)
        
        return results
    
    def is_initialized(self) -> bool:
        """Check if engine is initialized and ready."""
        return self._is_initialized and self.engine is not None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
