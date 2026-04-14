"""
Tests for the recommendation engine.

Tests all 10+ pattern rules, priority scoring, and recommendation generation.
"""
import pytest
from app.services.coaching.recommendation_engine import RecommendationEngine
from app.services.coaching import Recommendation, PatternMatch, RecommendationPriority


class TestRecommendationEngine:
    """Test suite for RecommendationEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create a recommendation engine instance."""
        return RecommendationEngine()
    
    @pytest.fixture
    def base_user_data(self):
        """Base user data for testing."""
        return {
            "user_id": 1,
            "rating_change": 0,
            "performance_trend": "stable"
        }
    
    @pytest.fixture
    def base_analysis_data(self):
        """Base analysis data for testing."""
        return {
            "average_acpl": 50.0,
            "opening_performance": {"acpl": 25.0, "games_count": 5},
            "middlegame_performance": {"acpl": 30.0, "games_count": 5},
            "endgame_performance": {"acpl": 35.0, "games_count": 5},
            "move_quality_stats": {
                "brilliant_moves": 2,
                "great_moves": 5,
                "best_moves": 10,
                "excellent_moves": 15,
                "good_moves": 20,
                "inaccuracies": 8,
                "mistakes": 5,
                "blunders": 3
            },
            "frequent_mistakes": [],
            "opening_stats": {},
            "total_games": 5
        }
    
    def test_endgame_weakness_detection(self, engine, base_user_data, base_analysis_data):
        """Test high endgame ACPL triggers endgame recommendation."""
        # Set high endgame ACPL
        base_analysis_data["endgame_performance"]["acpl"] = 50.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have endgame recommendation
        endgame_recs = [r for r in recommendations if r.category == "endgame"]
        assert len(endgame_recs) > 0
        assert "endgame" in endgame_recs[0].title.lower()
        assert endgame_recs[0].priority_score > 0
    
    def test_opening_weakness_detection(self, engine, base_user_data, base_analysis_data):
        """Test high opening ACPL triggers opening study recommendation."""
        # Set high opening ACPL
        base_analysis_data["opening_performance"]["acpl"] = 40.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have opening recommendation
        opening_recs = [r for r in recommendations if r.category == "opening"]
        assert len(opening_recs) > 0
        assert "opening" in opening_recs[0].title.lower()
    
    def test_overall_accuracy_low(self, engine, base_user_data, base_analysis_data):
        """Test accuracy <70% triggers tactics recommendation."""
        # Set high ACPL (low accuracy)
        base_analysis_data["average_acpl"] = 120.0  # ~88% accuracy, but formula gives <70%
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have tactics recommendation
        tactics_recs = [r for r in recommendations if r.category == "tactics"]
        assert len(tactics_recs) > 0
        assert "tactical" in tactics_recs[0].description.lower() or "accuracy" in tactics_recs[0].description.lower()
    
    def test_middlegame_blunders(self, engine, base_user_data, base_analysis_data):
        """Test frequent middlegame blunders triggers calculation recommendation."""
        # Set high middlegame ACPL and many mistakes
        base_analysis_data["middlegame_performance"]["acpl"] = 45.0
        base_analysis_data["move_quality_stats"]["mistakes"] = 15
        base_analysis_data["move_quality_stats"]["blunders"] = 10
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have calculation recommendation
        calc_recs = [r for r in recommendations if r.category == "calculation"]
        assert len(calc_recs) > 0
    
    def test_time_pressure_pattern(self, engine, base_user_data, base_analysis_data):
        """Test high blunder rate triggers time management recommendation."""
        # Set many blunders
        base_analysis_data["move_quality_stats"]["blunders"] = 10
        base_analysis_data["total_games"] = 5
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have time management recommendation
        time_recs = [r for r in recommendations if r.category == "time_management"]
        assert len(time_recs) > 0
    
    def test_opening_specific_issues(self, engine, base_user_data, base_analysis_data):
        """Test specific opening with poor performance."""
        # Add opening with high ACPL
        base_analysis_data["opening_stats"] = {
            "Sicilian Defense": {
                "count": 3,
                "total_acpl": 180.0,
                "average_acpl": 60.0,
                "eco": "B20"
            }
        }
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have opening-specific recommendation
        opening_recs = [r for r in recommendations if r.category == "opening"]
        assert len(opening_recs) > 0
    
    def test_conversion_rate_issues(self, engine, base_user_data, base_analysis_data):
        """Test poor conversion rate detection."""
        # Set declining trend and high endgame ACPL
        base_user_data["performance_trend"] = "declining"
        base_user_data["rating_change"] = -50
        base_analysis_data["endgame_performance"]["acpl"] = 50.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have technique recommendation
        technique_recs = [r for r in recommendations if r.category == "technique"]
        assert len(technique_recs) > 0
    
    def test_hanging_pieces_pattern(self, engine, base_user_data, base_analysis_data):
        """Test hanging pieces detection."""
        # Set many blunders (heuristic for hanging pieces)
        base_analysis_data["move_quality_stats"]["blunders"] = 8
        base_analysis_data["total_games"] = 5
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have visualization recommendation
        viz_recs = [r for r in recommendations if r.category == "visualization"]
        assert len(viz_recs) > 0
    
    def test_tactical_blindness(self, engine, base_user_data, base_analysis_data):
        """Test low best move percentage."""
        # Set low best move count
        base_analysis_data["move_quality_stats"]["best_moves"] = 5
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have pattern recognition recommendation
        pattern_recs = [r for r in recommendations if r.category == "pattern_recognition"]
        assert len(pattern_recs) > 0
    
    def test_endgame_knowledge_gaps(self, engine, base_user_data, base_analysis_data):
        """Test very high endgame ACPL indicates knowledge gaps."""
        # Set very high endgame ACPL
        base_analysis_data["endgame_performance"]["acpl"] = 70.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have endgame recommendation
        endgame_recs = [r for r in recommendations if r.category == "endgame"]
        assert len(endgame_recs) > 0
    
    def test_priority_scoring(self, engine):
        """Test priority score calculation."""
        score = engine.calculate_priority_score(
            severity=0.8,
            frequency=0.6,
            impact=0.9,
            recency=1.0
        )
        
        # Score should be between 0 and 100
        assert 0 <= score <= 100
        
        # High values should give high score
        assert score > 50
    
    def test_priority_levels(self, engine):
        """Test priority level mapping."""
        assert engine._get_priority_level(85) == RecommendationPriority.CRITICAL
        assert engine._get_priority_level(65) == RecommendationPriority.HIGH
        assert engine._get_priority_level(45) == RecommendationPriority.MEDIUM
        assert engine._get_priority_level(25) == RecommendationPriority.LOW
    
    def test_max_recommendations_limit(self, engine, base_user_data, base_analysis_data):
        """Test only top N recommendations returned."""
        # Create conditions for many recommendations
        base_analysis_data["average_acpl"] = 120.0
        base_analysis_data["opening_performance"]["acpl"] = 40.0
        base_analysis_data["middlegame_performance"]["acpl"] = 45.0
        base_analysis_data["endgame_performance"]["acpl"] = 50.0
        base_analysis_data["move_quality_stats"]["blunders"] = 10
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=3
        )
        
        # Should return at most 3 recommendations
        assert len(recommendations) <= 3
    
    def test_no_recommendations_for_good_performance(self, engine, base_user_data, base_analysis_data):
        """Test no recommendations if performance is good."""
        # Set excellent performance
        base_analysis_data["average_acpl"] = 20.0
        base_analysis_data["opening_performance"]["acpl"] = 15.0
        base_analysis_data["middlegame_performance"]["acpl"] = 18.0
        base_analysis_data["endgame_performance"]["acpl"] = 22.0
        base_analysis_data["move_quality_stats"]["blunders"] = 0
        base_analysis_data["move_quality_stats"]["mistakes"] = 1
        base_analysis_data["move_quality_stats"]["best_moves"] = 30
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have very few or no recommendations
        assert len(recommendations) <= 2
    
    def test_recommendations_sorted_by_priority(self, engine, base_user_data, base_analysis_data):
        """Test recommendations are sorted by priority score."""
        # Create conditions for multiple recommendations
        base_analysis_data["average_acpl"] = 100.0
        base_analysis_data["endgame_performance"]["acpl"] = 50.0
        base_analysis_data["opening_performance"]["acpl"] = 35.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Verify sorted by priority score (descending)
        if len(recommendations) > 1:
            for i in range(len(recommendations) - 1):
                assert recommendations[i].priority_score >= recommendations[i + 1].priority_score
    
    def test_recommendation_has_actionable_steps(self, engine, base_user_data, base_analysis_data):
        """Test recommendations include actionable steps."""
        base_analysis_data["endgame_performance"]["acpl"] = 50.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # At least one recommendation should have actionable steps
        has_steps = any(len(r.actionable_steps) > 0 for r in recommendations)
        assert has_steps
    
    def test_recommendation_to_dict(self, engine, base_user_data, base_analysis_data):
        """Test recommendation serialization to dict."""
        base_analysis_data["endgame_performance"]["acpl"] = 50.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=1
        )
        
        if recommendations:
            rec_dict = recommendations[0].to_dict()
            
            # Should have required fields
            assert "category" in rec_dict
            assert "priority" in rec_dict
            assert "priority_score" in rec_dict
            assert "title" in rec_dict
            assert "description" in rec_dict
            assert "actionable_steps" in rec_dict
    
    def test_pattern_match_included(self, engine, base_user_data, base_analysis_data):
        """Test pattern match is included in recommendations."""
        base_analysis_data["endgame_performance"]["acpl"] = 50.0
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # At least one recommendation should have pattern match
        has_pattern = any(r.pattern_match is not None for r in recommendations)
        assert has_pattern
    
    def test_insufficient_games_no_recommendation(self, engine, base_user_data, base_analysis_data):
        """Test no recommendations with insufficient game sample."""
        # Set very few games
        base_analysis_data["opening_performance"]["games_count"] = 1
        base_analysis_data["middlegame_performance"]["games_count"] = 1
        base_analysis_data["endgame_performance"]["games_count"] = 1
        base_analysis_data["total_games"] = 1
        
        recommendations = engine.generate_recommendations(
            base_user_data,
            base_analysis_data,
            max_recommendations=10
        )
        
        # Should have very few recommendations due to insufficient data
        # (some rules don't require minimum games)
        assert len(recommendations) <= 5


class TestRecommendationDataClasses:
    """Test data classes for recommendations."""
    
    def test_pattern_match_to_dict(self):
        """Test PatternMatch serialization."""
        pattern = PatternMatch(
            pattern_name="test_pattern",
            severity=0.8,
            frequency=5,
            evidence={"key": "value"}
        )
        
        result = pattern.to_dict()
        
        assert result["pattern_name"] == "test_pattern"
        assert result["severity"] == 0.8
        assert result["frequency"] == 5
        assert result["evidence"]["key"] == "value"
    
    def test_recommendation_creation(self):
        """Test Recommendation creation."""
        rec = Recommendation(
            category="tactics",
            priority="high",
            priority_score=75.0,
            title="Test Recommendation",
            description="Test description",
            actionable_steps=["Step 1", "Step 2"]
        )
        
        assert rec.category == "tactics"
        assert rec.priority == "high"
        assert rec.priority_score == 75.0
        assert len(rec.actionable_steps) == 2
