"""
Advanced pattern-based recommendation engine for chess coaching.

Analyzes user performance data and generates prioritized coaching recommendations
based on detected patterns and weaknesses.
"""
from typing import Dict, List, Optional, Any
from loguru import logger

from . import (
    Recommendation,
    PatternMatch,
    RecommendationCategory,
    RecommendationPriority
)


class RecommendationEngine:
    """
    Advanced pattern-based recommendation system.
    
    Analyzes user performance across multiple dimensions:
    - Phase-specific performance (opening, middlegame, endgame)
    - Move quality distribution
    - Tactical awareness
    - Time management
    - Opening repertoire
    - Conversion rate
    
    Generates prioritized recommendations with actionable steps.
    """
    
    # Thresholds for pattern detection
    ENDGAME_ACPL_THRESHOLD = 40.0
    OPENING_ACPL_THRESHOLD = 30.0
    MIDDLEGAME_ACPL_THRESHOLD = 35.0
    OVERALL_ACCURACY_THRESHOLD = 70.0
    BLUNDER_RATE_THRESHOLD = 0.3
    HANGING_PIECES_THRESHOLD = 0.2
    BEST_MOVE_RATE_THRESHOLD = 0.3
    
    def __init__(self):
        """Initialize the recommendation engine."""
        self.pattern_checkers = [
            self._check_endgame_weakness,
            self._check_opening_weakness,
            self._check_overall_accuracy,
            self._check_middlegame_blunders,
            self._check_time_pressure,
            self._check_opening_specific_issues,
            self._check_conversion_rate,
            self._check_hanging_pieces,
            self._check_tactical_blindness,
            self._check_endgame_knowledge,
        ]
    
    def generate_recommendations(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any],
        max_recommendations: int = 5
    ) -> List[Recommendation]:
        """
        Generate prioritized coaching recommendations.
        
        Args:
            user_data: User profile data (rating, trend, etc.)
            analysis_data: Aggregated analysis metrics
            max_recommendations: Maximum number of recommendations to return
        
        Returns:
            List of prioritized recommendations
        """
        recommendations = []
        
        # Run all pattern checkers
        for checker in self.pattern_checkers:
            try:
                rec = checker(user_data, analysis_data)
                if rec:
                    recommendations.append(rec)
            except Exception as e:
                logger.error(f"Error in pattern checker {checker.__name__}: {e}")
        
        # Sort by priority score (highest first)
        recommendations.sort(key=lambda r: r.priority_score, reverse=True)
        
        # Return top N recommendations
        return recommendations[:max_recommendations]
    
    def calculate_priority_score(
        self,
        severity: float,
        frequency: float,
        impact: float,
        recency: float = 1.0
    ) -> float:
        """
        Calculate priority score for a recommendation.
        
        Args:
            severity: How bad is the issue? (0-1)
            frequency: How often does it occur? (0-1)
            impact: Rating impact potential (0-1)
            recency: Recent games weighted higher (0-1)
        
        Returns:
            Priority score (0-100)
        """
        score = (
            severity * 0.4 +
            frequency * 0.3 +
            impact * 0.2 +
            recency * 0.1
        )
        return min(100.0, max(0.0, score * 100))
    
    def _get_priority_level(self, score: float) -> str:
        """Convert numeric score to priority level."""
        if score >= 80:
            return RecommendationPriority.CRITICAL
        elif score >= 60:
            return RecommendationPriority.HIGH
        elif score >= 40:
            return RecommendationPriority.MEDIUM
        else:
            return RecommendationPriority.LOW
    
    def _check_endgame_weakness(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for high endgame ACPL indicating endgame weakness."""
        endgame_perf = analysis_data.get("endgame_performance", {})
        endgame_acpl = endgame_perf.get("acpl", 0)
        games_count = endgame_perf.get("games_count", 0)
        
        if games_count < 3:  # Need minimum sample size
            return None
        
        if endgame_acpl > self.ENDGAME_ACPL_THRESHOLD:
            severity = min(1.0, endgame_acpl / 100.0)
            frequency = min(1.0, games_count / 10.0)
            impact = 0.8  # Endgame is critical for rating
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="high_endgame_acpl",
                severity=severity,
                frequency=games_count,
                evidence={"endgame_acpl": endgame_acpl, "games_count": games_count}
            )
            
            return Recommendation(
                category=RecommendationCategory.ENDGAME,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Endgame Technique Needs Improvement",
                description=f"Your endgame ACPL is {endgame_acpl:.1f}, which is above the recommended threshold. This suggests difficulty converting advantages or defending worse positions in the endgame.",
                actionable_steps=[
                    "Study fundamental endgames: King and Pawn, Rook endgames, opposite-colored bishops",
                    "Practice endgame positions on Lichess Studies or Chess.com Drills",
                    "Learn the Lucena and Philidor positions for rook endgames",
                    "Focus on calculation in simplified positions"
                ],
                resources=[
                    "Silman's Complete Endgame Course",
                    "Lichess Endgame Practice: https://lichess.org/practice"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_opening_weakness(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for high opening ACPL indicating opening preparation issues."""
        opening_perf = analysis_data.get("opening_performance", {})
        opening_acpl = opening_perf.get("acpl", 0)
        games_count = opening_perf.get("games_count", 0)
        
        if games_count < 3:
            return None
        
        if opening_acpl > self.OPENING_ACPL_THRESHOLD:
            severity = min(1.0, opening_acpl / 80.0)
            frequency = min(1.0, games_count / 10.0)
            impact = 0.7  # Opening sets the tone
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="high_opening_acpl",
                severity=severity,
                frequency=games_count,
                evidence={"opening_acpl": opening_acpl, "games_count": games_count}
            )
            
            return Recommendation(
                category=RecommendationCategory.OPENING,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Opening Repertoire Needs Work",
                description=f"Your opening ACPL is {opening_acpl:.1f}, indicating inaccuracies in the opening phase. This can lead to difficult middlegame positions.",
                actionable_steps=[
                    "Review your most-played openings and learn the main ideas",
                    "Study opening principles: control center, develop pieces, king safety",
                    "Build a consistent repertoire (1-2 openings as White, 1-2 defenses as Black)",
                    "Use opening explorer to understand typical plans"
                ],
                resources=[
                    "Chess.com Opening Explorer",
                    "Lichess Opening Database"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_overall_accuracy(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for overall accuracy below threshold."""
        average_acpl = analysis_data.get("average_acpl", 0)
        total_games = analysis_data.get("total_games", 0)
        
        if total_games < 3:
            return None
        
        # Convert ACPL to accuracy percentage
        accuracy = max(0, min(100, 100 - (average_acpl / 10)))
        
        if accuracy < self.OVERALL_ACCURACY_THRESHOLD:
            severity = min(1.0, (self.OVERALL_ACCURACY_THRESHOLD - accuracy) / 30.0)
            frequency = 1.0  # Affects all games
            impact = 0.9  # Critical for improvement
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="low_overall_accuracy",
                severity=severity,
                frequency=total_games,
                evidence={"accuracy": accuracy, "average_acpl": average_acpl}
            )
            
            return Recommendation(
                category=RecommendationCategory.TACTICS,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Focus on Tactical Training",
                description=f"Your overall accuracy is {accuracy:.1f}%, below the recommended 70%. This suggests frequent tactical oversights and calculation errors.",
                actionable_steps=[
                    "Solve 10-15 tactical puzzles daily on Chess.com or Lichess",
                    "Practice visualization: calculate 3-4 moves ahead before moving",
                    "Review your games and identify tactical mistakes",
                    "Study basic tactical patterns: pins, forks, skewers, discovered attacks"
                ],
                resources=[
                    "Chess.com Puzzles",
                    "Lichess Puzzle Rush",
                    "CT-ART 4.0 (Tactics training software)"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_middlegame_blunders(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for frequent blunders in the middlegame phase."""
        middlegame_perf = analysis_data.get("middlegame_performance", {})
        middlegame_acpl = middlegame_perf.get("acpl", 0)
        
        move_quality = analysis_data.get("move_quality_stats", {})
        total_mistakes = move_quality.get("mistakes", 0) + move_quality.get("blunders", 0)
        total_moves = sum(move_quality.values()) if move_quality else 1
        
        mistake_rate = total_mistakes / max(1, total_moves)
        
        if middlegame_acpl > self.MIDDLEGAME_ACPL_THRESHOLD and mistake_rate > 0.15:
            severity = min(1.0, middlegame_acpl / 100.0)
            frequency = min(1.0, mistake_rate * 3)
            impact = 0.85  # Middlegame is where games are often decided
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="middlegame_blunders",
                severity=severity,
                frequency=total_mistakes,
                evidence={
                    "middlegame_acpl": middlegame_acpl,
                    "mistake_rate": mistake_rate,
                    "total_mistakes": total_mistakes
                }
            )
            
            return Recommendation(
                category=RecommendationCategory.CALCULATION,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Improve Middlegame Calculation",
                description=f"Your middlegame ACPL is {middlegame_acpl:.1f} with a {mistake_rate*100:.1f}% mistake rate. This indicates calculation issues in complex positions.",
                actionable_steps=[
                    "Practice calculating forcing sequences (checks, captures, threats)",
                    "Use the 'candidate moves' method: identify 2-3 moves before calculating",
                    "Slow down in critical positions - take your time",
                    "Study master games to understand typical middlegame plans"
                ],
                resources=[
                    "Aagaard's Calculation books",
                    "Analyze master games on ChessBase"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_time_pressure(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for time pressure patterns (blunders in late game)."""
        move_quality = analysis_data.get("move_quality_stats", {})
        blunders = move_quality.get("blunders", 0)
        total_games = analysis_data.get("total_games", 1)
        
        # Heuristic: if blunder rate is high, likely time pressure
        blunder_per_game = blunders / max(1, total_games)
        
        if blunder_per_game > 1.5:  # More than 1.5 blunders per game
            severity = min(1.0, blunder_per_game / 3.0)
            frequency = min(1.0, blunders / 20.0)
            impact = 0.75
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="time_pressure_blunders",
                severity=severity,
                frequency=blunders,
                evidence={"blunders": blunders, "blunder_per_game": blunder_per_game}
            )
            
            return Recommendation(
                category=RecommendationCategory.TIME_MANAGEMENT,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Improve Time Management",
                description=f"You're averaging {blunder_per_game:.1f} blunders per game, which often indicates time pressure. Better time management can prevent costly mistakes.",
                actionable_steps=[
                    "Allocate time wisely: spend more time on critical positions",
                    "Move faster in simple/forced positions",
                    "Practice with increment time controls to build time cushion",
                    "Set a time threshold (e.g., 30 seconds) to avoid panic moves"
                ],
                resources=[
                    "Practice with longer time controls initially",
                    "Use pre-moves only for obvious recaptures"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_opening_specific_issues(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for specific openings with poor performance."""
        opening_stats = analysis_data.get("opening_stats", {})
        
        if not opening_stats:
            return None
        
        # Find opening with worst ACPL and sufficient games
        worst_opening = None
        worst_acpl = 0
        
        for opening_name, stats in opening_stats.items():
            count = stats.get("count", 0)
            avg_acpl = stats.get("average_acpl", 0)
            
            if count >= 2 and avg_acpl > worst_acpl:
                worst_acpl = avg_acpl
                worst_opening = opening_name
        
        if worst_opening and worst_acpl > 50:
            severity = min(1.0, worst_acpl / 100.0)
            frequency = min(1.0, opening_stats[worst_opening]["count"] / 5.0)
            impact = 0.65
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="opening_specific_weakness",
                severity=severity,
                frequency=opening_stats[worst_opening]["count"],
                evidence={
                    "opening": worst_opening,
                    "acpl": worst_acpl,
                    "count": opening_stats[worst_opening]["count"]
                }
            )
            
            return Recommendation(
                category=RecommendationCategory.OPENING,
                priority=self._get_priority_level(score),
                priority_score=score,
                title=f"Study {worst_opening} Opening",
                description=f"Your performance in {worst_opening} is weak (ACPL: {worst_acpl:.1f}). Consider studying this opening specifically or switching to a different line.",
                actionable_steps=[
                    f"Review games where you played {worst_opening}",
                    "Study the main ideas and typical plans for this opening",
                    "Watch YouTube videos or read articles about this opening",
                    "Consider switching to a different opening if consistently struggling"
                ],
                resources=[
                    f"Search '{worst_opening}' on YouTube",
                    "Chess.com Opening Explorer"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_conversion_rate(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for poor conversion rate (winning positions to wins)."""
        # This is a heuristic based on endgame performance and rating trend
        endgame_perf = analysis_data.get("endgame_performance", {})
        endgame_acpl = endgame_perf.get("acpl", 0)
        
        performance_trend = user_data.get("performance_trend", "stable")
        rating_change = user_data.get("rating_change", 0)
        
        # If endgame is weak and rating is declining, likely conversion issues
        if endgame_acpl > 45 and (performance_trend == "declining" or rating_change < -30):
            severity = 0.7
            frequency = 0.6
            impact = 0.8
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="poor_conversion",
                severity=severity,
                frequency=1,
                evidence={
                    "endgame_acpl": endgame_acpl,
                    "rating_change": rating_change,
                    "trend": performance_trend
                }
            )
            
            return Recommendation(
                category=RecommendationCategory.TECHNIQUE,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Improve Winning Technique",
                description="You may be struggling to convert winning positions into wins. Better technique in favorable positions is crucial for rating improvement.",
                actionable_steps=[
                    "Study how to convert material advantages (extra pawn, piece)",
                    "Learn the principle of two weaknesses in winning positions",
                    "Practice trading pieces when ahead in material",
                    "Avoid unnecessary complications when winning"
                ],
                resources=[
                    "Silman's 'How to Reassess Your Chess'",
                    "Study endgame technique"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_hanging_pieces(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for frequent hanging pieces (visualization issue)."""
        move_quality = analysis_data.get("move_quality_stats", {})
        blunders = move_quality.get("blunders", 0)
        total_games = analysis_data.get("total_games", 1)
        
        # Heuristic: assume 20-30% of blunders are hanging pieces
        estimated_hangs = blunders * 0.25
        hang_rate = estimated_hangs / max(1, total_games)
        
        if hang_rate > 0.5:  # More than 0.5 hanging pieces per game
            severity = min(1.0, hang_rate / 1.5)
            frequency = min(1.0, estimated_hangs / 10.0)
            impact = 0.85  # Hanging pieces are critical errors
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="hanging_pieces",
                severity=severity,
                frequency=int(estimated_hangs),
                evidence={"estimated_hangs": estimated_hangs, "hang_rate": hang_rate}
            )
            
            return Recommendation(
                category=RecommendationCategory.VISUALIZATION,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Reduce Hanging Pieces",
                description=f"You're frequently leaving pieces undefended (estimated {hang_rate:.1f} per game). This indicates visualization and board awareness issues.",
                actionable_steps=[
                    "Before every move, check: 'Is this piece defended?'",
                    "Practice visualization exercises: set up positions and find undefended pieces",
                    "Slow down and scan the board before moving",
                    "Use the 'touch-move' rule in practice to force careful consideration"
                ],
                resources=[
                    "Visualization training apps",
                    "Practice blindfold chess (start with simple positions)"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_tactical_blindness(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for low best move percentage (missing tactics)."""
        move_quality = analysis_data.get("move_quality_stats", {})
        best_moves = move_quality.get("best_moves", 0)
        total_moves = sum(move_quality.values()) if move_quality else 1
        
        best_move_rate = best_moves / max(1, total_moves)
        
        if best_move_rate < self.BEST_MOVE_RATE_THRESHOLD:
            severity = min(1.0, (self.BEST_MOVE_RATE_THRESHOLD - best_move_rate) / 0.3)
            frequency = 1.0
            impact = 0.8
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="tactical_blindness",
                severity=severity,
                frequency=total_moves,
                evidence={"best_move_rate": best_move_rate, "best_moves": best_moves}
            )
            
            return Recommendation(
                category=RecommendationCategory.PATTERN_RECOGNITION,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Improve Tactical Pattern Recognition",
                description=f"Your best move rate is {best_move_rate*100:.1f}%, suggesting you're missing tactical opportunities. Better pattern recognition will help you find strong moves.",
                actionable_steps=[
                    "Study common tactical motifs: forks, pins, skewers, discovered attacks",
                    "Solve themed tactical puzzles (e.g., 'pin' puzzles, 'fork' puzzles)",
                    "Review your games and identify missed tactical opportunities",
                    "Practice pattern recognition: quickly identify piece relationships"
                ],
                resources=[
                    "Chess Tactics for Beginners by Weteschnik",
                    "Lichess Puzzle Themes"
                ],
                pattern_match=pattern
            )
        
        return None
    
    def _check_endgame_knowledge(
        self,
        user_data: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Optional[Recommendation]:
        """Check for specific endgame knowledge gaps."""
        endgame_perf = analysis_data.get("endgame_performance", {})
        endgame_acpl = endgame_perf.get("acpl", 0)
        games_count = endgame_perf.get("games_count", 0)
        
        # If endgame ACPL is very high, likely knowledge gaps
        if games_count >= 3 and endgame_acpl > 60:
            severity = min(1.0, endgame_acpl / 120.0)
            frequency = min(1.0, games_count / 10.0)
            impact = 0.75
            
            score = self.calculate_priority_score(severity, frequency, impact)
            
            pattern = PatternMatch(
                pattern_name="endgame_knowledge_gaps",
                severity=severity,
                frequency=games_count,
                evidence={"endgame_acpl": endgame_acpl, "games_count": games_count}
            )
            
            return Recommendation(
                category=RecommendationCategory.ENDGAME,
                priority=self._get_priority_level(score),
                priority_score=score,
                title="Study Fundamental Endgames",
                description=f"Your endgame ACPL of {endgame_acpl:.1f} suggests knowledge gaps in basic endgame positions. Learning fundamental endgames will significantly improve your results.",
                actionable_steps=[
                    "Master King and Pawn endgames (opposition, key squares)",
                    "Learn basic Rook endgames (Lucena, Philidor positions)",
                    "Study Queen vs Pawn endgames",
                    "Practice endgame drills on Lichess or Chess.com"
                ],
                resources=[
                    "100 Endgames You Must Know by Jesus de la Villa",
                    "Lichess Endgame Practice"
                ],
                pattern_match=pattern
            )
        
        return None
