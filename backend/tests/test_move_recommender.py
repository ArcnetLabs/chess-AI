"""Tests for move recommendation service."""

import pytest
import chess
from app.services.moves.move_recommender import MoveRecommender
from app.services.moves import TacticalTheme, MoveDifficulty
from app.services.engine.stockfish_engine import StockfishEngine


@pytest.fixture
async def move_recommender():
    """Create move recommender instance."""
    engine = StockfishEngine(depth=15, threads=1)
    recommender = MoveRecommender(stockfish_engine=engine)
    yield recommender
    await engine.close()


@pytest.mark.asyncio
async def test_analyze_starting_position(move_recommender):
    """Test analyzing the starting position."""
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    analysis = await move_recommender.analyze_position(fen, num_moves=5, depth=15)
    
    assert analysis is not None
    assert analysis.fen == fen
    assert len(analysis.candidate_moves) == 5
    assert analysis.phase == "opening"
    assert analysis.material_balance == 0
    
    # Check best move is reasonable
    best_move = analysis.candidate_moves[0]
    assert best_move.rank == 1
    assert best_move.move in ["e4", "d4", "Nf3", "c4"]  # Common opening moves
    assert TacticalTheme.DEVELOPMENT in best_move.tactical_themes or \
           TacticalTheme.CENTER_CONTROL in best_move.tactical_themes


@pytest.mark.asyncio
async def test_analyze_tactical_position(move_recommender):
    """Test analyzing a tactical position with a fork."""
    # Position where Nf6+ forks king and queen
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    
    analysis = await move_recommender.analyze_position(fen, num_moves=3, depth=15)
    
    assert analysis is not None
    assert len(analysis.candidate_moves) >= 1
    
    # Check that tactical themes are detected
    all_themes = set()
    for move in analysis.candidate_moves:
        all_themes.update(move.tactical_themes)
    
    assert len(all_themes) > 0


@pytest.mark.asyncio
async def test_compare_moves(move_recommender):
    """Test comparing two moves."""
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    moves = ["e4", "e3"]
    
    comparison = await move_recommender.compare_moves(fen, moves, depth=15)
    
    assert "comparisons" in comparison
    assert "recommendation" in comparison
    assert len(comparison["comparisons"]) == 2
    
    # e4 should be better than e3
    e4_eval = next(c["evaluation"] for c in comparison["comparisons"] if c["move"] == "e4")
    e3_eval = next(c["evaluation"] for c in comparison["comparisons"] if c["move"] == "e3")
    assert e4_eval >= e3_eval


@pytest.mark.asyncio
async def test_move_recommendation_structure(move_recommender):
    """Test that move recommendations have all required fields."""
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    
    analysis = await move_recommender.analyze_position(fen, num_moves=3, depth=15)
    
    for move_rec in analysis.candidate_moves:
        # Check all required fields are present
        assert move_rec.move is not None
        assert move_rec.uci is not None
        assert move_rec.evaluation is not None
        assert move_rec.rank > 0
        assert move_rec.explanation is not None
        assert isinstance(move_rec.tactical_themes, list)
        assert isinstance(move_rec.variations, list)
        assert isinstance(move_rec.pros, list)
        assert isinstance(move_rec.cons, list)
        assert move_rec.difficulty in [d.value for d in MoveDifficulty]
        
        # Check serialization works
        move_dict = move_rec.to_dict()
        assert "move" in move_dict
        assert "evaluation" in move_dict
        assert "explanation" in move_dict


@pytest.mark.asyncio
async def test_detect_game_phase(move_recommender):
    """Test game phase detection."""
    # Opening position
    opening_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    opening_analysis = await move_recommender.analyze_position(opening_fen, num_moves=1, depth=10)
    assert opening_analysis.phase == "opening"
    
    # Endgame position (few pieces)
    endgame_fen = "8/5k2/8/8/8/8/5K2/8 w - - 0 1"
    endgame_analysis = await move_recommender.analyze_position(endgame_fen, num_moves=1, depth=10)
    assert endgame_analysis.phase == "endgame"


@pytest.mark.asyncio
async def test_material_balance(move_recommender):
    """Test material balance calculation."""
    # Equal material
    equal_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    equal_analysis = await move_recommender.analyze_position(equal_fen, num_moves=1, depth=10)
    assert equal_analysis.material_balance == 0
    
    # White up a queen
    white_up_fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    white_up_analysis = await move_recommender.analyze_position(white_up_fen, num_moves=1, depth=10)
    assert white_up_analysis.material_balance > 0


@pytest.mark.asyncio
async def test_position_insights(move_recommender):
    """Test that position insights are generated."""
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    analysis = await move_recommender.analyze_position(fen, num_moves=3, depth=15)
    
    assert analysis.insights is not None
    assert len(analysis.insights) > 0
    assert "advantage" in analysis.insights.lower() or "equal" in analysis.insights.lower()


@pytest.mark.asyncio
async def test_serialization(move_recommender):
    """Test that analysis can be serialized to dict."""
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    analysis = await move_recommender.analyze_position(fen, num_moves=3, depth=15)
    
    # Should not raise exception
    analysis_dict = analysis.to_dict()
    
    assert "fen" in analysis_dict
    assert "evaluation" in analysis_dict
    assert "candidate_moves" in analysis_dict
    assert "insights" in analysis_dict
    assert isinstance(analysis_dict["candidate_moves"], list)


if __name__ == "__main__":
    # Run tests manually
    import asyncio
    
    async def run_tests():
        recommender = MoveRecommender(StockfishEngine(depth=15, threads=1))
        
        print("Testing starting position analysis...")
        await test_analyze_starting_position(recommender)
        print("✓ Starting position test passed")
        
        print("\nTesting tactical position...")
        await test_analyze_tactical_position(recommender)
        print("✓ Tactical position test passed")
        
        print("\nTesting move comparison...")
        await test_compare_moves(recommender)
        print("✓ Move comparison test passed")
        
        print("\nTesting move recommendation structure...")
        await test_move_recommendation_structure(recommender)
        print("✓ Structure test passed")
        
        print("\nTesting game phase detection...")
        await test_detect_game_phase(recommender)
        print("✓ Phase detection test passed")
        
        print("\nTesting material balance...")
        await test_material_balance(recommender)
        print("✓ Material balance test passed")
        
        print("\nTesting position insights...")
        await test_position_insights(recommender)
        print("✓ Insights test passed")
        
        print("\nTesting serialization...")
        await test_serialization(recommender)
        print("✓ Serialization test passed")
        
        await recommender.engine.close()
        print("\n✅ All tests passed!")
    
    asyncio.run(run_tests())
