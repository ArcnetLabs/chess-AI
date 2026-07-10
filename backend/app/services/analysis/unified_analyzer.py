"""Unified chess game analyzer using the new StockfishEngine wrapper."""

import io
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import chess
import chess.pgn
from loguru import logger

from ..engine.engine_pool import get_pooled_engine
from ..engine.stockfish_engine import StockfishEngine, StockfishEngineError


@dataclass
class MoveAnalysis:
    """Analysis result for a single move."""
    move_number: int
    move_san: str
    move_uci: str
    fen_before: str
    fen_after: str
    evaluation_cp: Optional[float]
    mate_in: Optional[int]
    best_move_uci: Optional[str]
    evaluation_change: Optional[float]
    classification: str  # brilliant, great, best, excellent, good, inaccuracy, mistake, blunder
    is_user_move: bool


@dataclass
class PhaseAnalysis:
    """Analysis for a game phase (opening/middlegame/endgame)."""
    phase_name: str
    move_range: tuple
    average_acpl: float
    move_count: int
    blunders: int
    mistakes: int
    inaccuracies: int
    best_moves: int


@dataclass
class GameAnalysisResult:
    """Complete game analysis result."""
    # Game metadata
    game_id: Optional[str]
    user_color: str
    total_moves: int
    
    # Overall metrics
    user_acpl: float
    opponent_acpl: Optional[float]
    accuracy_percentage: float
    
    # Move classifications (user only)
    brilliant_moves: int = 0
    great_moves: int = 0
    best_moves: int = 0
    excellent_moves: int = 0
    good_moves: int = 0
    inaccuracies: int = 0
    mistakes: int = 0
    blunders: int = 0
    
    # Phase analysis
    opening_phase: Optional[PhaseAnalysis] = None
    middlegame_phase: Optional[PhaseAnalysis] = None
    endgame_phase: Optional[PhaseAnalysis] = None
    
    # Opening information
    opening_name: Optional[str] = None
    opening_eco: Optional[str] = None
    
    # Detailed move data
    all_moves: List[MoveAnalysis] = None
    critical_positions: List[MoveAnalysis] = None
    
    # Analysis metadata
    engine_version: str = "Stockfish 17"
    analysis_depth: int = 15
    analysis_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class UnifiedChessAnalyzer:
    """
    Unified chess game analyzer using StockfishEngine.
    
    Analyzes complete games and provides:
    - Move-by-move evaluation
    - Move quality classification
    - Phase-based analysis (opening/middlegame/endgame)
    - ACPL and accuracy metrics
    - Critical position identification
    """
    
    # Move classification thresholds (centipawn loss)
    THRESHOLDS = {
        'brilliant': -50,     # Exceptional move (sacrifice, etc.)
        'great': -25,         # Very strong move
        'best': 0,            # Engine's top choice
        'excellent': 25,      # Near-optimal
        'good': 50,           # Reasonable
        'inaccuracy': 100,    # Minor error
        'mistake': 200,       # Significant error
        'blunder': 300        # Major blunder
    }
    
    def __init__(self, engine: Optional[StockfishEngine] = None):
        """
        Initialize analyzer.
        
        Args:
            engine: Optional injected StockfishEngine (tests only).
                Production code uses the global engine pool.
        """
        self.engine = engine
        self._engine_injected = engine is not None
    
    async def analyze_game(
        self,
        pgn_string: str,
        user_color: str,
        game_id: Optional[str] = None
    ) -> Optional[GameAnalysisResult]:
        """
        Analyze a complete chess game.
        
        Args:
            pgn_string: PGN string of the game
            user_color: 'white' or 'black' - which side is the user
            game_id: Optional game identifier
        
        Returns:
            GameAnalysisResult or None if analysis fails
        """
        start_time = datetime.now()
        
        try:
            # Get engine from pool if needed
            if self.engine is None:
                self.engine = await get_pooled_engine()
            elif not self.engine.is_initialized():
                await self.engine.initialize()
            
            # Parse PGN
            game = self._parse_pgn(pgn_string)
            if not game:
                logger.error("Failed to parse PGN")
                return None
            
            # Extract opening info
            opening_name = game.headers.get("Opening")
            opening_eco = game.headers.get("ECO")
            
            # Analyze all moves
            all_moves = await self._analyze_all_moves(game, user_color)
            
            if not all_moves:
                logger.error("No moves to analyze")
                return None
            
            # Filter user moves
            user_moves = [m for m in all_moves if m.is_user_move]
            opponent_moves = [m for m in all_moves if not m.is_user_move]
            
            # Calculate metrics
            user_acpl = self._calculate_acpl(user_moves)
            opponent_acpl = self._calculate_acpl(opponent_moves) if opponent_moves else None
            accuracy = self._acpl_to_accuracy(user_acpl)
            
            # Classify moves
            classifications = self._classify_moves(user_moves)
            
            # Analyze phases
            opening, middlegame, endgame = self._analyze_phases(user_moves, len(all_moves))
            
            # Find critical positions
            critical = [m for m in user_moves if abs(m.evaluation_change or 0) > 150]
            
            # Calculate analysis time
            analysis_duration = (datetime.now() - start_time).total_seconds()
            
            result = GameAnalysisResult(
                game_id=game_id,
                user_color=user_color,
                total_moves=len(user_moves),
                user_acpl=user_acpl,
                opponent_acpl=opponent_acpl,
                accuracy_percentage=accuracy,
                opening_name=opening_name,
                opening_eco=opening_eco,
                all_moves=all_moves,
                critical_positions=critical,
                opening_phase=opening,
                middlegame_phase=middlegame,
                endgame_phase=endgame,
                analysis_depth=self.engine.depth,
                analysis_time_seconds=analysis_duration,
                **classifications
            )
            
            logger.info(
                f"Game {game_id} analyzed: {user_acpl:.1f} ACPL, "
                f"{accuracy:.1f}% accuracy, {classifications['blunders']} blunders "
                f"(⏱️ {analysis_duration:.1f}s)"
            )
            
            return result
            
        except StockfishEngineError as e:
            logger.error(f"Engine error during analysis: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
            return None
    
    def _parse_pgn(self, pgn_string: str) -> Optional[chess.pgn.Game]:
        """Parse PGN string into chess.pgn.Game object."""
        try:
            pgn_io = io.StringIO(pgn_string)
            game = chess.pgn.read_game(pgn_io)
            return game
        except Exception as e:
            logger.error(f"PGN parsing error: {e}")
            return None
    
    async def _analyze_all_moves(
        self,
        game: chess.pgn.Game,
        user_color: str
    ) -> List[MoveAnalysis]:
        """Analyze all moves in the game."""
        moves_analysis = []
        board = game.board()
        
        # Get initial position evaluation
        prev_eval = await self.engine.evaluate_position(board)
        prev_cp = prev_eval['evaluation_cp'] or 0
        
        move_number = 0
        
        for node in game.mainline():
            move_number += 1
            move = node.move
            fen_before = board.fen()
            
            # Get SAN notation BEFORE pushing the move
            move_san = board.san(move)
            move_uci = move.uci()
            
            # Make the move
            board.push(move)
            fen_after = board.fen()
            
            # Evaluate position after move
            current_eval = await self.engine.evaluate_position(board)
            current_cp = current_eval['evaluation_cp'] or 0
            mate_in = current_eval['mate_in']
            best_move = current_eval['best_move']
            
            # Determine whose move it was
            is_white_move = (move_number % 2 == 1)
            is_user_move = (user_color == 'white' and is_white_move) or \
                          (user_color == 'black' and not is_white_move)
            
            # Calculate evaluation change from player's perspective
            # Flip evaluation if it's black's turn
            if not is_white_move:
                prev_cp = -prev_cp
                current_cp = -current_cp
            
            eval_change = prev_cp - current_cp  # Loss in centipawns
            
            # Classify move
            is_best = (move_uci == best_move)
            classification = self._classify_single_move(eval_change, is_best)
            
            move_analysis = MoveAnalysis(
                move_number=move_number,
                move_san=move_san,
                move_uci=move_uci,
                fen_before=fen_before,
                fen_after=fen_after,
                evaluation_cp=current_cp,
                mate_in=mate_in,
                best_move_uci=best_move,
                evaluation_change=eval_change,
                classification=classification,
                is_user_move=is_user_move
            )
            
            moves_analysis.append(move_analysis)
            prev_cp = current_cp
        
        return moves_analysis
    
    def _classify_single_move(self, cp_loss: float, is_best: bool) -> str:
        """Classify a single move based on centipawn loss."""
        if is_best or cp_loss <= self.THRESHOLDS['best']:
            return 'best'
        elif cp_loss <= self.THRESHOLDS['excellent']:
            return 'excellent'
        elif cp_loss <= self.THRESHOLDS['good']:
            return 'good'
        elif cp_loss <= self.THRESHOLDS['inaccuracy']:
            return 'inaccuracy'
        elif cp_loss <= self.THRESHOLDS['mistake']:
            return 'mistake'
        else:
            return 'blunder'
    
    def _classify_moves(self, moves: List[MoveAnalysis]) -> Dict[str, int]:
        """Count move classifications."""
        return {
            'brilliant_moves': len([m for m in moves if m.classification == 'brilliant']),
            'great_moves': len([m for m in moves if m.classification == 'great']),
            'best_moves': len([m for m in moves if m.classification == 'best']),
            'excellent_moves': len([m for m in moves if m.classification == 'excellent']),
            'good_moves': len([m for m in moves if m.classification == 'good']),
            'inaccuracies': len([m for m in moves if m.classification == 'inaccuracy']),
            'mistakes': len([m for m in moves if m.classification == 'mistake']),
            'blunders': len([m for m in moves if m.classification == 'blunder']),
        }
    
    def _calculate_acpl(self, moves: List[MoveAnalysis]) -> float:
        """Calculate Average Centipawn Loss."""
        if not moves:
            return 0.0
        
        total_loss = sum(abs(m.evaluation_change or 0) for m in moves)
        return total_loss / len(moves)
    
    def _acpl_to_accuracy(self, acpl: float) -> float:
        """Convert ACPL to accuracy percentage (0-100)."""
        # Piecewise linear mapping
        if acpl < 10:
            return 99.0
        elif acpl < 20:
            return 95.0 + (20 - acpl)
        elif acpl < 50:
            return 80.0 + (50 - acpl) / 2
        elif acpl < 100:
            return 60.0 + (100 - acpl) / 2.5
        else:
            return max(0, 60.0 - (acpl - 100) / 5)
    
    def _analyze_phases(
        self,
        user_moves: List[MoveAnalysis],
        total_moves: int
    ) -> tuple:
        """Analyze game phases."""
        # Define phase boundaries
        opening_end = min(20, total_moves // 3)
        endgame_start = max(opening_end + 10, total_moves * 2 // 3)
        
        def create_phase(name: str, start: int, end: int) -> PhaseAnalysis:
            phase_moves = [m for m in user_moves if start <= m.move_number < end]
            
            if not phase_moves:
                return PhaseAnalysis(name, (start, end), 0.0, 0, 0, 0, 0, 0)
            
            acpl = self._calculate_acpl(phase_moves)
            classifications = self._classify_moves(phase_moves)
            
            return PhaseAnalysis(
                phase_name=name,
                move_range=(start, end),
                average_acpl=acpl,
                move_count=len(phase_moves),
                blunders=classifications['blunders'],
                mistakes=classifications['mistakes'],
                inaccuracies=classifications['inaccuracies'],
                best_moves=classifications['best_moves']
            )
        
        opening = create_phase("opening", 1, opening_end)
        middlegame = create_phase("middlegame", opening_end, endgame_start)
        endgame = create_phase("endgame", endgame_start, total_moves + 1)
        
        return opening, middlegame, endgame
    
    async def close(self):
        """Close the engine only when injected for tests (never pool engines)."""
        if self._engine_injected and self.engine:
            await self.engine.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit — only close injected test engines."""
        if self._engine_injected:
            await self.close()
