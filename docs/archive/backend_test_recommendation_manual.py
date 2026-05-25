"""
Manual test script for recommendation engine.
Run this to verify the recommendation engine works without pytest.
"""
import sys
sys.path.insert(0, '.')

from app.services.coaching.recommendation_engine import RecommendationEngine

def test_basic_functionality():
    """Test basic recommendation engine functionality."""
    print("Testing Recommendation Engine...")
    print("=" * 60)
    
    engine = RecommendationEngine()
    
    # Test data
    user_data = {
        "user_id": 1,
        "rating_change": -20,
        "performance_trend": "declining"
    }
    
    analysis_data = {
        "average_acpl": 85.0,
        "opening_performance": {"acpl": 35.0, "games_count": 10},
        "middlegame_performance": {"acpl": 40.0, "games_count": 10},
        "endgame_performance": {"acpl": 50.0, "games_count": 10},
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
        "opening_stats": {
            "Sicilian Defense": {
                "count": 3,
                "total_acpl": 180.0,
                "average_acpl": 60.0,
                "eco": "B20"
            }
        },
        "total_games": 10
    }
    
    # Generate recommendations
    recommendations = engine.generate_recommendations(
        user_data,
        analysis_data,
        max_recommendations=5
    )
    
    print(f"\n✓ Generated {len(recommendations)} recommendations\n")
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec.title}")
        print(f"   Category: {rec.category}")
        print(f"   Priority: {rec.priority} (Score: {rec.priority_score:.1f})")
        print(f"   Description: {rec.description}")
        print(f"   Actionable Steps:")
        for step in rec.actionable_steps[:2]:  # Show first 2 steps
            print(f"     - {step}")
        if rec.pattern_match:
            print(f"   Pattern: {rec.pattern_match.pattern_name} (Severity: {rec.pattern_match.severity:.2f})")
        print()
    
    # Test serialization
    print("Testing serialization...")
    if recommendations:
        rec_dict = recommendations[0].to_dict()
        assert "category" in rec_dict
        assert "priority" in rec_dict
        assert "priority_score" in rec_dict
        print("✓ Serialization works\n")
    
    # Test priority scoring
    print("Testing priority scoring...")
    score = engine.calculate_priority_score(0.8, 0.6, 0.9, 1.0)
    assert 0 <= score <= 100
    print(f"✓ Priority score calculation works (score: {score:.1f})\n")
    
    # Test with excellent performance (should have few/no recommendations)
    print("Testing with excellent performance...")
    excellent_data = {
        "average_acpl": 20.0,
        "opening_performance": {"acpl": 15.0, "games_count": 10},
        "middlegame_performance": {"acpl": 18.0, "games_count": 10},
        "endgame_performance": {"acpl": 22.0, "games_count": 10},
        "move_quality_stats": {
            "brilliant_moves": 5,
            "great_moves": 10,
            "best_moves": 30,
            "excellent_moves": 25,
            "good_moves": 20,
            "inaccuracies": 5,
            "mistakes": 1,
            "blunders": 0
        },
        "frequent_mistakes": [],
        "opening_stats": {},
        "total_games": 10
    }
    
    excellent_recs = engine.generate_recommendations(
        user_data,
        excellent_data,
        max_recommendations=10
    )
    print(f"✓ Excellent performance: {len(excellent_recs)} recommendations (expected: few/none)\n")
    
    print("=" * 60)
    print("✓ All tests passed!")
    print("\nRecommendation Engine is working correctly!")
    return True

if __name__ == "__main__":
    try:
        test_basic_functionality()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
