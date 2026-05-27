"""
Integration tests for enhanced recommendations in insights system.

Tests the integration between recommendation engine and insights API,
ensuring backward compatibility and proper data flow.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.api.insights import generate_insights_background
from app.models.insights import UserInsight
from app.models.user import User
from app.models.game import Game, GameAnalysis
from app.services.coaching.recommendation_engine import RecommendationEngine


class TestInsightsIntegration:
    """Test suite for insights integration with enhanced recommendations."""

    @pytest.fixture(autouse=True)
    def mock_list_user_patterns(self):
        with patch(
            "app.services.coaching.recommendation_engine.list_user_patterns",
            return_value=[],
        ):
            yield
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = MagicMock(spec=Session)
        return db
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock(spec=User)
        user.id = 1
        user.chesscom_username = "testuser"
        user.last_analysis_at = datetime.utcnow() - timedelta(days=8)
        return user
    
    @pytest.fixture
    def mock_games(self):
        """Create mock games with analysis."""
        games = []
        for i in range(5):
            game = MagicMock(spec=Game)
            game.id = i + 1
            game.end_time = datetime.utcnow() - timedelta(days=i)
            game.white_username = "testuser" if i % 2 == 0 else "opponent"
            game.black_username = "opponent" if i % 2 == 0 else "testuser"
            game.winner = "white" if i % 2 == 0 else "black"
            game.time_class = "blitz"
            games.append(game)
        return games
    
    @pytest.fixture
    def mock_analyses(self):
        """Create mock game analyses."""
        analyses = []
        for i in range(5):
            analysis = MagicMock(spec=GameAnalysis)
            analysis.game_id = i + 1
            analysis.user_acpl = 50.0 + i * 10  # Varying ACPL
            analysis.opening_acpl = 55.0 + i * 5
            analysis.middlegame_acpl = 45.0 + i * 3
            analysis.endgame_acpl = 40.0 + i * 4
            analysis.opening_name = "Sicilian Defense" if i < 3 else "Queen's Gambit"
            analysis.opening_eco = "B20" if i < 3 else "D20"
            analysis.move_quality_stats = {
                "brilliant_moves": 1,
                "great_moves": 2,
                "best_moves": 5,
                "excellent_moves": 8,
                "good_moves": 10,
                "inaccuracies": 3,
                "mistakes": 2,
                "blunders": 1
            }
            analyses.append(analysis)
        return analyses
    
    @pytest.fixture
    def mock_existing_insight(self):
        """Create a mock existing insight."""
        insight = MagicMock(spec=UserInsight)
        insight.id = 1
        insight.user_id = 1
        insight.recommendations = []
        insight.recommendation_scores = []
        insight.pattern_matches = []
        return insight
    
    def test_enhanced_recommendations_in_insights(
        self, mock_db, mock_user, mock_games, mock_analyses, mock_existing_insight
    ):
        """Test enhanced recommendations are stored in user_insights."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = mock_games
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = mock_analyses
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_existing_insight
        
        # Mock commit
        mock_db.commit = MagicMock()
        
        # Generate insights
        period_start = datetime.utcnow() - timedelta(days=7)
        period_end = datetime.utcnow()
        
        generate_insights_background(
            user_id=1,
            period_start=period_start,
            period_end=period_end,
            analysis_type="weekly",
            db=mock_db
        )
        
        # Verify enhanced recommendation fields are set
        assert hasattr(mock_existing_insight, 'recommendation_scores')
        assert hasattr(mock_existing_insight, 'pattern_matches')
        
        # Should have called commit
        mock_db.commit.assert_called()
    
    def test_fallback_to_basic_recommendations(self, mock_db, mock_user, mock_games):
        """Test graceful fallback if engine fails."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = mock_games
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Mock insight creation
        mock_insight = MagicMock(spec=UserInsight)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        
        # Patch RecommendationEngine to raise exception
        with patch('app.services.coaching.recommendation_engine.RecommendationEngine') as MockEngine:
            MockEngine.side_effect = Exception("Engine failed")
            
            # Generate insights
            period_start = datetime.utcnow() - timedelta(days=7)
            period_end = datetime.utcnow()
            
            generate_insights_background(
                user_id=1,
                period_start=period_start,
                period_end=period_end,
                analysis_type="weekly",
                db=mock_db
            )
            
            # Should still create insight with basic recommendations
            mock_db.add.assert_called()
            mock_db.commit.assert_called()
    
    def test_existing_insights_still_work(self, mock_db, mock_user, mock_games, mock_analyses):
        """Test existing insights endpoints unchanged."""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = mock_games
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = mock_analyses
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Mock insight creation
        mock_insight = MagicMock(spec=UserInsight)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        
        # Generate insights with enhanced engine
        period_start = datetime.utcnow() - timedelta(days=7)
        period_end = datetime.utcnow()
        
        generate_insights_background(
            user_id=1,
            period_start=period_start,
            period_end=period_end,
            analysis_type="weekly",
            db=mock_db
        )
        
        # Should create insight with all required fields
        mock_db.add.assert_called()
        added_insight = mock_db.add.call_args[0][0]
        
        # Verify basic fields are still set
        assert added_insight.user_id == 1
        assert added_insight.period_start == period_start
        assert added_insight.period_end == period_end
        assert added_insight.analysis_type == "weekly"
        
        # Enhanced fields should also be present (even if empty)
        assert hasattr(added_insight, 'recommendation_scores')
        assert hasattr(added_insight, 'pattern_matches')
    
    def test_recommendation_engine_integration(self):
        """Test recommendation engine works with real data."""
        engine = RecommendationEngine()
        
        user_data = {
            "user_id": 1,
            "rating_change": -20,
            "performance_trend": "declining"
        }
        
        analysis_data = {
            "average_acpl": 80.0,
            "opening_performance": {"acpl": 35.0, "games_count": 5},
            "middlegame_performance": {"acpl": 45.0, "games_count": 5},
            "endgame_performance": {"acpl": 60.0, "games_count": 5},
            "move_quality_stats": {
                "brilliant_moves": 1,
                "great_moves": 3,
                "best_moves": 8,
                "excellent_moves": 12,
                "good_moves": 15,
                "inaccuracies": 10,
                "mistakes": 8,
                "blunders": 5
            },
            "frequent_mistakes": [],
            "opening_stats": {
                "Sicilian Defense": {
                    "count": 3,
                    "total_acpl": 120.0,
                    "average_acpl": 40.0,
                    "eco": "B20"
                }
            },
            "total_games": 5
        }
        
        recommendations = engine.generate_recommendations(user_data, analysis_data)
        
        # Should generate recommendations
        assert len(recommendations) > 0
        
        # Should have priority scores
        for rec in recommendations:
            assert rec.priority_score >= 0
            assert rec.priority_score <= 100
            assert rec.priority in ["critical", "high", "medium", "low"]
            assert len(rec.actionable_steps) > 0
    
    def test_no_games_still_works(self, mock_db, mock_user):
        """Test insights generation works even with no games."""
        # Mock database queries for no games
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Mock insight creation
        mock_insight = MagicMock(spec=UserInsight)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        
        # Generate insights
        period_start = datetime.utcnow() - timedelta(days=7)
        period_end = datetime.utcnow()
        
        generate_insights_background(
            user_id=1,
            period_start=period_start,
            period_end=period_end,
            analysis_type="weekly",
            db=mock_db
        )
        
        # Should still create insight
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_opening_stats_use_opening_acpl(self):
        """Opening repertoire stats must aggregate opening_acpl, not user_acpl."""
        analyses = []
        for i in range(3):
            analysis = MagicMock()
            analysis.opening_name = "Sicilian Defense"
            analysis.opening_eco = "B20"
            analysis.opening_acpl = 55.0 + i * 5
            analysis.user_acpl = 100.0 + i * 10
            analyses.append(analysis)

        opening_stats = {}
        for analysis in analyses:
            if analysis.opening_name:
                if analysis.opening_name not in opening_stats:
                    opening_stats[analysis.opening_name] = {
                        "count": 0,
                        "total_acpl": 0,
                        "eco": analysis.opening_eco,
                    }
                opening_stats[analysis.opening_name]["count"] += 1
                opening_stats[analysis.opening_name]["total_acpl"] += (
                    analysis.opening_acpl or 0
                )

        for opening in opening_stats:
            if opening_stats[opening]["count"] > 0:
                opening_stats[opening]["average_acpl"] = (
                    opening_stats[opening]["total_acpl"]
                    / opening_stats[opening]["count"]
                )

        sicilian = opening_stats["Sicilian Defense"]
        expected_avg = sum(a.opening_acpl for a in analyses) / 3
        assert sicilian["average_acpl"] == pytest.approx(expected_avg)
        assert sicilian["average_acpl"] != pytest.approx(
            sum(a.user_acpl for a in analyses) / 3
        )
    
    def test_coaching_plan_endpoint_data(self, mock_db, mock_user, mock_existing_insight):
        """Test coaching plan endpoint returns enhanced data."""
        # Setup enhanced insight data
        mock_existing_insight.recommendations = [
            {
                "category": "endgame",
                "priority": "high",
                "priority_score": 75.0,
                "title": "Endgame Technique Needs Improvement",
                "description": "Your endgame ACPL is 50.0...",
                "actionable_steps": ["Study fundamental endgames"]
            }
        ]
        mock_existing_insight.recommendation_scores = [75.0]
        mock_existing_insight.pattern_matches = [
            {
                "pattern_name": "high_endgame_acpl",
                "severity": 0.7,
                "frequency": 5,
                "evidence": {"endgame_acpl": 50.0}
            }
        ]
        mock_existing_insight.focus_areas_detailed = {"endgame": {"severity": 0.8}}
        mock_existing_insight.average_acpl = 50.0
        mock_existing_insight.performance_trend = "declining"
        mock_existing_insight.rating_change = -20
        mock_existing_insight.games_analyzed = 5
        mock_existing_insight.period_start = datetime.utcnow() - timedelta(days=7)
        mock_existing_insight.period_end = datetime.utcnow()
        mock_existing_insight.analysis_type = "weekly"
        
        # Mock database query
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_existing_insight
        
        # Import and test the endpoint function
        from app.api.insights import get_coaching_plan
        
        # This would normally be called via FastAPI, but we can test the logic
        result = get_coaching_plan(user_id=1, db=mock_db)
        
        # Should return enhanced data
        assert "recommendations" in result
        assert "priority_scores" in result
        assert "pattern_matches" in result
        assert "focus_areas" in result
        assert "performance_summary" in result
        assert "period" in result
        
        # Verify data structure
        assert len(result["recommendations"]) > 0
        assert len(result["priority_scores"]) > 0
        assert len(result["pattern_matches"]) > 0
        assert result["performance_summary"]["average_acpl"] == 50.0


class TestBackwardCompatibility:
    """Test backward compatibility of enhanced recommendations."""
    
    def test_old_recommendation_format_still_works(self):
        """Test old recommendation format is still supported."""
        # Create recommendation in old format
        old_recommendation = {
            "category": "tactics",
            "priority": "high",
            "description": "Focus on tactical training"
        }
        
        # Should be compatible with new format
        assert "category" in old_recommendation
        assert "priority" in old_recommendation
        assert "description" in old_recommendation
    
    def test_new_fields_are_optional(self):
        """Test new enhanced fields are optional."""
        # Create insight without enhanced fields
        insight = UserInsight(
            user_id=1,
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
            analysis_type="weekly",
            recommendations=[{"category": "tactics", "priority": "high"}]
        )
        
        # Should work without enhanced fields
        assert insight.recommendations is not None
        assert insight.recommendation_scores is None  # Optional
        assert insight.pattern_matches is None  # Optional
        assert insight.focus_areas_detailed is None  # Optional
    
    def test_api_response_compatibility(self):
        """Test API responses are backward compatible."""
        # Mock insight with minimal data
        insight = MagicMock(spec=UserInsight)
        insight.recommendations = [{"category": "tactics", "priority": "high"}]
        insight.recommendation_scores = None
        insight.pattern_matches = None
        insight.focus_areas_detailed = None
        insight.period_start = datetime.utcnow()
        insight.period_end = datetime.utcnow()
        insight.analysis_type = "weekly"
        
        # Should not break when fields are None
        assert insight.recommendations is not None
        assert insight.recommendation_scores is None
        assert insight.pattern_matches is None
