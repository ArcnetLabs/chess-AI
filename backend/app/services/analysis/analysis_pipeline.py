"""Analysis pipeline for move classification, ACPL, and recommendations."""

from typing import Dict, List, Optional
from loguru import logger


class AnalysisPipeline:
    """Pipeline for analyzing games and generating insights."""
    
    @staticmethod
    def classify_move(eval_delta: float, is_mate: bool = False) -> str:
        """
        Classify a move based on evaluation delta.
        
        Args:
            eval_delta: Centipawn difference (positive = bad for player)
            is_mate: Whether position involves mate
        
        Returns:
            Move classification string
        """
        if is_mate:
            return "blunder" if eval_delta > 0 else "brilliant"
        
        if eval_delta >= 200:
            return "blunder"
        elif eval_delta >= 100:
            return "mistake"
        elif eval_delta >= 50:
            return "inaccuracy"
        elif eval_delta <= -100:
            return "brilliant"
        elif eval_delta <= -50:
            return "great"
        elif eval_delta <= -10:
            return "best"
        elif eval_delta <= 10:
            return "excellent"
        else:
            return "good"
    
    @staticmethod
    def calculate_acpl(eval_deltas: List[float]) -> float:
        """
        Calculate Average Centipawn Loss.
        
        Args:
            eval_deltas: List of centipawn losses
        
        Returns:
            ACPL value
        """
        if not eval_deltas:
            return 0.0
        return sum(abs(delta) for delta in eval_deltas) / len(eval_deltas)
    
    @staticmethod
    def map_acpl_to_accuracy(acpl: float) -> float:
        """
        Map ACPL to accuracy percentage (0-100).
        
        Args:
            acpl: Average centipawn loss
        
        Returns:
            Accuracy percentage
        """
        if acpl < 20:
            return 95 + (20 - acpl) / 20 * 5
        elif acpl < 50:
            return 80 + (50 - acpl) / 30 * 15
        elif acpl < 100:
            return 60 + (100 - acpl) / 50 * 20
        else:
            return max(0, 60 - (acpl - 100) / 10)
    
    @staticmethod
    def detect_phase(move_number: int, total_moves: int) -> str:
        """
        Detect game phase based on move number.
        
        Args:
            move_number: Current move number
            total_moves: Total moves in game
        
        Returns:
            Phase name: "opening", "middlegame", or "endgame"
        """
        if move_number <= 12:
            return "opening"
        elif move_number <= 30:
            return "middlegame"
        else:
            return "endgame"
    
    @staticmethod
    def generate_recommendations(analysis_summary: Dict) -> List[Dict]:
        """
        Generate coaching recommendations based on analysis.
        
        Args:
            analysis_summary: Dictionary with analysis metrics
        
        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        
        # Check accuracy
        accuracy = analysis_summary.get("accuracy_percentage", 0)
        if accuracy < 70:
            recommendations.append({
                "category": "tactics",
                "priority": "high",
                "description": "Overall accuracy is below 70%. Focus on tactical training.",
                "improvement": "Practice tactical puzzles daily to improve calculation."
            })
        
        # Check phase performance
        phase_perf = analysis_summary.get("phase_performance", {})
        endgame_acpl = phase_perf.get("endgame_acpl", 0)
        if endgame_acpl > 40:
            recommendations.append({
                "category": "endgame",
                "priority": "high",
                "description": "Endgame ACPL is high. Your endgame technique needs work.",
                "improvement": "Study fundamental endgames and practice conversion."
            })
        
        opening_acpl = phase_perf.get("opening_acpl", 0)
        if opening_acpl > 30:
            recommendations.append({
                "category": "opening",
                "priority": "medium",
                "description": "Opening phase shows inaccuracies.",
                "improvement": "Review your opening repertoire and learn key principles."
            })
        
        return recommendations[:5]  # Return top 5
