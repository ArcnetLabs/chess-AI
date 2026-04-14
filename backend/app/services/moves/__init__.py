"""Move recommendation and analysis services."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class TacticalTheme(str, Enum):
    """Tactical themes that can be detected in positions."""
    PIN = "pin"
    FORK = "fork"
    SKEWER = "skewer"
    DISCOVERED_ATTACK = "discovered_attack"
    DOUBLE_ATTACK = "double_attack"
    SACRIFICE = "sacrifice"
    CHECKMATE_THREAT = "checkmate_threat"
    BACK_RANK = "back_rank"
    PAWN_BREAK = "pawn_break"
    DEVELOPMENT = "development"
    CENTER_CONTROL = "center_control"
    KING_SAFETY = "king_safety"
    PIECE_COORDINATION = "piece_coordination"
    HANGING_PIECE = "hanging_piece"
    TRAPPED_PIECE = "trapped_piece"


class MoveDifficulty(str, Enum):
    """Difficulty level of understanding a move."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MASTER = "master"


@dataclass
class MoveRecommendation:
    """Represents a recommended move with analysis."""
    
    move: str  # SAN notation (e.g., "Nf3")
    uci: str  # UCI notation (e.g., "g1f3")
    evaluation: float  # Centipawn evaluation
    rank: int  # 1 = best, 2 = second best, etc.
    explanation: str  # Natural language explanation
    tactical_themes: List[TacticalTheme]  # Detected tactical themes
    variations: List[str]  # Sample variations
    pros: List[str]  # Advantages of this move
    cons: List[str]  # Disadvantages of this move
    difficulty: MoveDifficulty  # How hard to understand
    mate_in: Optional[int] = None  # Moves to mate if applicable
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "move": self.move,
            "uci": self.uci,
            "evaluation": self.evaluation,
            "rank": self.rank,
            "explanation": self.explanation,
            "tactical_themes": [theme.value for theme in self.tactical_themes],
            "variations": self.variations,
            "pros": self.pros,
            "cons": self.cons,
            "difficulty": self.difficulty.value,
            "mate_in": self.mate_in
        }


@dataclass
class PositionAnalysis:
    """Complete analysis of a chess position."""
    
    fen: str  # Position in FEN notation
    evaluation: float  # Overall position evaluation
    best_move: str  # Best move in SAN
    candidate_moves: List[MoveRecommendation]  # Top move recommendations
    tactical_themes: List[TacticalTheme]  # Themes present in position
    phase: str  # opening, middlegame, endgame
    material_balance: int  # Material count difference
    insights: str  # Overall position assessment
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "fen": self.fen,
            "evaluation": self.evaluation,
            "best_move": self.best_move,
            "candidate_moves": [move.to_dict() for move in self.candidate_moves],
            "tactical_themes": [theme.value for theme in self.tactical_themes],
            "phase": self.phase,
            "material_balance": self.material_balance,
            "insights": self.insights
        }
