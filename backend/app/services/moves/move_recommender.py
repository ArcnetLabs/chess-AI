"""Move recommendation service with Stockfish integration."""

import chess
from typing import List, Optional, Dict, Any
from loguru import logger

from ..engine.stockfish_engine import StockfishEngine, StockfishEngineError
from . import (
    MoveRecommendation,
    PositionAnalysis,
    TacticalTheme,
    MoveDifficulty
)


class MoveRecommender:
    """
    Service for analyzing positions and recommending moves.
    
    Uses Stockfish for position evaluation and generates educational
    explanations for move recommendations.
    """
    
    def __init__(self, stockfish_engine: Optional[StockfishEngine] = None):
        """
        Initialize move recommender.
        
        Args:
            stockfish_engine: Stockfish engine instance (creates new if None)
        """
        self.engine = stockfish_engine or StockfishEngine(depth=18, threads=2)
    
    async def analyze_position(
        self,
        fen: str,
        num_moves: int = 5,
        depth: int = 18
    ) -> PositionAnalysis:
        """
        Analyze a position and return top move recommendations.
        
        Args:
            fen: Position in FEN notation
            num_moves: Number of candidate moves to analyze
            depth: Stockfish search depth
        
        Returns:
            PositionAnalysis with move recommendations
        """
        try:
            # Parse position
            board = chess.Board(fen)
            
            # Initialize engine if needed
            if not self.engine.is_initialized():
                await self.engine.initialize()
            
            # Get multi-PV analysis (top N moves)
            candidate_moves = await self._get_candidate_moves(
                board, num_moves, depth
            )
            
            # Detect game phase
            phase = self._detect_phase(board)
            
            # Calculate material balance
            material_balance = self._calculate_material_balance(board)
            
            # Detect tactical themes in position
            position_themes = self._detect_position_themes(board, candidate_moves)
            
            # Generate overall insights
            insights = self._generate_position_insights(
                board, candidate_moves[0] if candidate_moves else None, phase
            )
            
            # Get best move evaluation
            best_eval = candidate_moves[0].evaluation if candidate_moves else 0.0
            best_move = candidate_moves[0].move if candidate_moves else "No legal moves"
            
            return PositionAnalysis(
                fen=fen,
                evaluation=best_eval,
                best_move=best_move,
                candidate_moves=candidate_moves,
                tactical_themes=position_themes,
                phase=phase,
                material_balance=material_balance,
                insights=insights
            )
            
        except Exception as e:
            logger.error(f"Position analysis failed: {e}")
            raise
    
    async def _get_candidate_moves(
        self,
        board: chess.Board,
        num_moves: int,
        depth: int
    ) -> List[MoveRecommendation]:
        """Get top N candidate moves with analysis."""
        
        # Get all legal moves
        legal_moves = list(board.legal_moves)
        
        if not legal_moves:
            return []
        
        # Analyze each move
        move_evaluations = []
        
        for move in legal_moves[:min(20, len(legal_moves))]:  # Limit to top 20 for performance
            # Make move on copy
            temp_board = board.copy()
            temp_board.push(move)
            
            # Evaluate resulting position
            eval_result = await self.engine.evaluate_position(temp_board, depth=depth)
            
            # Flip evaluation (we want it from current player's perspective)
            if eval_result["evaluation_cp"] is not None:
                evaluation = -eval_result["evaluation_cp"] / 100.0  # Convert to pawns
            else:
                # Mate score
                evaluation = 100.0 if eval_result["mate_in"] and eval_result["mate_in"] > 0 else -100.0
            
            move_evaluations.append({
                "move": move,
                "evaluation": evaluation,
                "mate_in": -eval_result["mate_in"] if eval_result["mate_in"] else None,
                "pv": eval_result.get("pv", [])
            })
        
        # Sort by evaluation (best first)
        move_evaluations.sort(key=lambda x: x["evaluation"], reverse=True)
        
        # Take top N moves
        top_moves = move_evaluations[:num_moves]
        
        # Generate recommendations
        recommendations = []
        for rank, move_data in enumerate(top_moves, 1):
            move = move_data["move"]
            
            recommendation = await self._create_move_recommendation(
                board, move, move_data, rank
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    async def _create_move_recommendation(
        self,
        board: chess.Board,
        move: chess.Move,
        move_data: Dict[str, Any],
        rank: int
    ) -> MoveRecommendation:
        """Create a detailed move recommendation."""
        
        # Convert to SAN notation
        san_move = board.san(move)
        uci_move = move.uci()
        
        # Detect tactical themes for this move
        themes = self._detect_move_themes(board, move)
        
        # Generate explanation
        explanation = self._generate_move_explanation(
            board, move, move_data, themes
        )
        
        # Generate pros and cons
        pros, cons = self._generate_pros_cons(board, move, move_data, themes)
        
        # Generate sample variation
        variations = self._generate_variations(move_data.get("pv", []))
        
        # Determine difficulty
        difficulty = self._determine_difficulty(themes, move_data["evaluation"])
        
        return MoveRecommendation(
            move=san_move,
            uci=uci_move,
            evaluation=move_data["evaluation"],
            rank=rank,
            explanation=explanation,
            tactical_themes=themes,
            variations=variations,
            pros=pros,
            cons=cons,
            difficulty=difficulty,
            mate_in=move_data.get("mate_in")
        )
    
    def _detect_move_themes(
        self,
        board: chess.Board,
        move: chess.Move
    ) -> List[TacticalTheme]:
        """Detect tactical themes in a move."""
        themes = []
        
        # Make move on copy to analyze
        temp_board = board.copy()
        piece = board.piece_at(move.from_square)
        
        if not piece:
            return themes
        
        # Check for captures
        if board.is_capture(move):
            themes.append(TacticalTheme.DOUBLE_ATTACK)
        
        # Check for checks
        temp_board.push(move)
        if temp_board.is_check():
            themes.append(TacticalTheme.CHECKMATE_THREAT)
        
        # Development (moving piece from starting square)
        if self._is_development_move(board, move):
            themes.append(TacticalTheme.DEVELOPMENT)
        
        # Center control (moving to or attacking center squares)
        if self._controls_center(move):
            themes.append(TacticalTheme.CENTER_CONTROL)
        
        # Castling = king safety
        if board.is_castling(move):
            themes.append(TacticalTheme.KING_SAFETY)
        
        # Check for pins, forks, skewers (simplified detection)
        if self._creates_fork(board, move):
            themes.append(TacticalTheme.FORK)
        
        if self._creates_pin(board, move):
            themes.append(TacticalTheme.PIN)
        
        return themes if themes else [TacticalTheme.PIECE_COORDINATION]
    
    def _is_development_move(self, board: chess.Board, move: chess.Move) -> bool:
        """Check if move develops a piece."""
        piece = board.piece_at(move.from_square)
        if not piece:
            return False
        
        # Check if piece is on starting square
        if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            starting_rank = 0 if piece.color == chess.WHITE else 7
            return chess.square_rank(move.from_square) == starting_rank
        
        return False
    
    def _controls_center(self, move: chess.Move) -> bool:
        """Check if move controls center squares."""
        center_squares = [chess.E4, chess.E5, chess.D4, chess.D5]
        return move.to_square in center_squares
    
    def _creates_fork(self, board: chess.Board, move: chess.Move) -> bool:
        """Simplified fork detection."""
        temp_board = board.copy()
        temp_board.push(move)
        
        # Check if the moved piece attacks multiple valuable pieces
        piece = temp_board.piece_at(move.to_square)
        if not piece:
            return False
        
        attacks = temp_board.attacks(move.to_square)
        attacked_pieces = [
            temp_board.piece_at(sq) for sq in attacks
            if temp_board.piece_at(sq) and temp_board.piece_at(sq).color != piece.color
        ]
        
        # Fork if attacking 2+ pieces
        return len(attacked_pieces) >= 2
    
    def _creates_pin(self, board: chess.Board, move: chess.Move) -> bool:
        """Simplified pin detection."""
        # This is a basic implementation
        # A full implementation would check for pieces pinned to king/queen
        return False
    
    def _generate_move_explanation(
        self,
        board: chess.Board,
        move: chess.Move,
        move_data: Dict[str, Any],
        themes: List[TacticalTheme]
    ) -> str:
        """Generate natural language explanation for a move."""
        
        piece = board.piece_at(move.from_square)
        piece_name = chess.piece_name(piece.piece_type).capitalize() if piece else "Piece"
        
        san_move = board.san(move)
        eval_score = move_data["evaluation"]
        
        # Start with basic move description
        if move_data.get("mate_in"):
            explanation = f"{san_move} leads to checkmate in {abs(move_data['mate_in'])} moves."
        elif eval_score > 3:
            explanation = f"{san_move} gives a winning advantage ({eval_score:+.1f})."
        elif eval_score > 1:
            explanation = f"{san_move} provides a significant advantage ({eval_score:+.1f})."
        elif eval_score > 0.3:
            explanation = f"{san_move} gives a slight edge ({eval_score:+.1f})."
        elif eval_score > -0.3:
            explanation = f"{san_move} maintains equality ({eval_score:+.1f})."
        else:
            explanation = f"{san_move} is playable but slightly worse ({eval_score:+.1f})."
        
        # Add tactical theme descriptions
        if TacticalTheme.FORK in themes:
            explanation += f" This {piece_name.lower()} move creates a fork, attacking multiple pieces."
        elif TacticalTheme.PIN in themes:
            explanation += " This move pins an opponent's piece."
        elif TacticalTheme.DEVELOPMENT in themes:
            explanation += f" Develops the {piece_name.lower()} to an active square."
        elif TacticalTheme.CENTER_CONTROL in themes:
            explanation += " Controls important central squares."
        elif TacticalTheme.KING_SAFETY in themes:
            explanation += " Improves king safety."
        
        return explanation
    
    def _generate_pros_cons(
        self,
        board: chess.Board,
        move: chess.Move,
        move_data: Dict[str, Any],
        themes: List[TacticalTheme]
    ) -> tuple[List[str], List[str]]:
        """Generate pros and cons for a move."""
        
        pros = []
        cons = []
        
        # Pros based on themes
        if TacticalTheme.DEVELOPMENT in themes:
            pros.append("Develops a piece to an active square")
        if TacticalTheme.CENTER_CONTROL in themes:
            pros.append("Controls the center")
        if TacticalTheme.KING_SAFETY in themes:
            pros.append("Improves king safety")
        if TacticalTheme.FORK in themes:
            pros.append("Attacks multiple pieces")
        if TacticalTheme.CHECKMATE_THREAT in themes:
            pros.append("Creates threats against the king")
        
        # Evaluation-based pros
        if move_data["evaluation"] > 1:
            pros.append("Strong positional advantage")
        
        # Cons (simplified)
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured and captured.piece_type == chess.PAWN:
                cons.append("Captures only a pawn")
        
        # Default pros/cons if empty
        if not pros:
            pros.append("Solid move maintaining position")
        if not cons:
            cons.append("No significant drawbacks")
        
        return pros, cons
    
    def _generate_variations(self, pv: List[str]) -> List[str]:
        """Generate sample variations from principal variation."""
        if not pv:
            return []
        
        # Take first 5 moves of PV
        variation_moves = pv[:5]
        variation_str = " ".join(variation_moves)
        
        return [f"Sample line: {variation_str}"]
    
    def _determine_difficulty(
        self,
        themes: List[TacticalTheme],
        evaluation: float
    ) -> MoveDifficulty:
        """Determine difficulty level of understanding the move."""
        
        # Tactical moves are easier to understand
        tactical_themes = {
            TacticalTheme.FORK, TacticalTheme.PIN, TacticalTheme.CHECKMATE_THREAT
        }
        
        if any(theme in tactical_themes for theme in themes):
            return MoveDifficulty.BEGINNER
        
        # Clear advantage = intermediate
        if abs(evaluation) > 1.5:
            return MoveDifficulty.INTERMEDIATE
        
        # Positional moves = advanced
        if TacticalTheme.PIECE_COORDINATION in themes:
            return MoveDifficulty.ADVANCED
        
        return MoveDifficulty.INTERMEDIATE
    
    def _detect_phase(self, board: chess.Board) -> str:
        """Detect game phase (opening, middlegame, endgame)."""
        
        # Count pieces
        piece_count = len(board.piece_map())
        
        # Count queens
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        
        # Endgame: few pieces or no queens
        if piece_count <= 12 or queens == 0:
            return "endgame"
        
        # Opening: many pieces and early moves
        if piece_count >= 28:
            return "opening"
        
        return "middlegame"
    
    def _calculate_material_balance(self, board: chess.Board) -> int:
        """Calculate material balance in centipawns."""
        
        piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 0
        }
        
        white_material = 0
        black_material = 0
        
        for piece_type in piece_values:
            white_material += len(board.pieces(piece_type, chess.WHITE)) * piece_values[piece_type]
            black_material += len(board.pieces(piece_type, chess.BLACK)) * piece_values[piece_type]
        
        return white_material - black_material
    
    def _detect_position_themes(
        self,
        board: chess.Board,
        candidate_moves: List[MoveRecommendation]
    ) -> List[TacticalTheme]:
        """Detect tactical themes present in the position."""
        
        themes = set()
        
        # Aggregate themes from candidate moves
        for move_rec in candidate_moves[:3]:  # Top 3 moves
            themes.update(move_rec.tactical_themes)
        
        # Check position-specific themes
        if board.is_check():
            themes.add(TacticalTheme.CHECKMATE_THREAT)
        
        return list(themes)
    
    def _generate_position_insights(
        self,
        board: chess.Board,
        best_move: Optional[MoveRecommendation],
        phase: str
    ) -> str:
        """Generate overall position insights."""
        
        if not best_move:
            return "No legal moves available."
        
        eval_score = best_move.evaluation
        
        # Determine who is better
        if eval_score > 2:
            advantage = "White has a winning advantage"
        elif eval_score > 0.5:
            advantage = "White has a clear advantage"
        elif eval_score > 0:
            advantage = "White has a slight edge"
        elif eval_score > -0.5:
            advantage = "The position is roughly equal"
        elif eval_score > -2:
            advantage = "Black has a clear advantage"
        else:
            advantage = "Black has a winning advantage"
        
        # Add phase-specific insights
        phase_insight = {
            "opening": "Focus on development and center control.",
            "middlegame": "Look for tactical opportunities and piece coordination.",
            "endgame": "Activate your king and create passed pawns."
        }.get(phase, "")
        
        return f"{advantage}. {phase_insight}"
    
    async def compare_moves(
        self,
        fen: str,
        moves: List[str],
        depth: int = 18
    ) -> Dict[str, Any]:
        """
        Compare multiple moves and explain differences.
        
        Args:
            fen: Position in FEN notation
            moves: List of moves in SAN or UCI notation
            depth: Analysis depth
        
        Returns:
            Comparison dictionary with explanations
        """
        board = chess.Board(fen)
        
        if not self.engine.is_initialized():
            await self.engine.initialize()
        
        comparisons = []
        
        for move_str in moves:
            try:
                # Try to parse as SAN or UCI
                try:
                    move = board.parse_san(move_str)
                except:
                    move = chess.Move.from_uci(move_str)
                
                # Analyze move
                temp_board = board.copy()
                temp_board.push(move)
                
                eval_result = await self.engine.evaluate_position(temp_board, depth=depth)
                evaluation = -eval_result["evaluation_cp"] / 100.0 if eval_result["evaluation_cp"] is not None else 0
                
                comparisons.append({
                    "move": board.san(move),
                    "evaluation": evaluation,
                    "mate_in": -eval_result["mate_in"] if eval_result["mate_in"] else None
                })
                
            except Exception as e:
                logger.error(f"Error analyzing move {move_str}: {e}")
                continue
        
        # Sort by evaluation
        comparisons.sort(key=lambda x: x["evaluation"], reverse=True)
        
        # Generate comparison text
        if len(comparisons) >= 2:
            best = comparisons[0]
            worst = comparisons[-1]
            diff = best["evaluation"] - worst["evaluation"]
            
            recommendation = f"{best['move']} is better than {worst['move']} by {diff:.2f} pawns."
        else:
            recommendation = "Not enough valid moves to compare."
        
        return {
            "comparisons": comparisons,
            "recommendation": recommendation
        }
