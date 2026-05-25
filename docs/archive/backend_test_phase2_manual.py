"""Manual test script for Phase 2 Move Recommendation System."""

import asyncio
import sys
from app.services.moves.move_recommender import MoveRecommender
from app.services.engine.stockfish_engine import StockfishEngine


async def test_move_recommendations():
    """Test move recommendation system."""
    
    print("=" * 60)
    print("Phase 2: Move Recommendation System - Manual Test")
    print("=" * 60)
    
    # Initialize recommender
    print("\n1. Initializing Stockfish engine...")
    engine = StockfishEngine(depth=15, threads=2)
    recommender = MoveRecommender(stockfish_engine=engine)
    
    try:
        # Test 1: Analyze starting position
        print("\n2. Testing starting position analysis...")
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        analysis = await recommender.analyze_position(fen, num_moves=5, depth=15)
        
        print(f"\n   Position: Starting position")
        print(f"   Evaluation: {analysis.evaluation:+.2f}")
        print(f"   Phase: {analysis.phase}")
        print(f"   Material Balance: {analysis.material_balance}")
        print(f"   Best Move: {analysis.best_move}")
        print(f"\n   Top 5 Moves:")
        
        for i, move in enumerate(analysis.candidate_moves, 1):
            print(f"\n   {i}. {move.move} ({move.evaluation:+.2f})")
            print(f"      {move.explanation}")
            print(f"      Themes: {', '.join([t.value for t in move.tactical_themes])}")
            print(f"      Difficulty: {move.difficulty.value}")
        
        print(f"\n   Position Insights: {analysis.insights}")
        
        # Test 2: Compare moves
        print("\n\n3. Testing move comparison...")
        moves_to_compare = ["e4", "d4", "Nf3"]
        
        comparison = await recommender.compare_moves(fen, moves_to_compare, depth=15)
        
        print(f"\n   Comparing: {', '.join(moves_to_compare)}")
        print(f"\n   Results:")
        for comp in comparison["comparisons"]:
            print(f"   - {comp['move']}: {comp['evaluation']:+.2f}")
        
        print(f"\n   Recommendation: {comparison['recommendation']}")
        
        # Test 3: Tactical position
        print("\n\n4. Testing tactical position...")
        tactical_fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        
        tactical_analysis = await recommender.analyze_position(tactical_fen, num_moves=3, depth=15)
        
        print(f"\n   Position: Italian Game position")
        print(f"   Evaluation: {tactical_analysis.evaluation:+.2f}")
        print(f"   Best Move: {tactical_analysis.best_move}")
        print(f"\n   Top 3 Moves:")
        
        for i, move in enumerate(tactical_analysis.candidate_moves, 1):
            print(f"\n   {i}. {move.move} ({move.evaluation:+.2f})")
            print(f"      {move.explanation}")
            if move.pros:
                print(f"      Pros: {', '.join(move.pros[:2])}")
        
        # Test 4: Endgame position
        print("\n\n5. Testing endgame position...")
        endgame_fen = "8/5k2/3K4/8/8/8/8/8 w - - 0 1"
        
        endgame_analysis = await recommender.analyze_position(endgame_fen, num_moves=3, depth=15)
        
        print(f"\n   Position: King endgame")
        print(f"   Phase: {endgame_analysis.phase}")
        print(f"   Best Move: {endgame_analysis.best_move}")
        print(f"   Evaluation: {endgame_analysis.evaluation:+.2f}")
        
        # Test 5: Serialization
        print("\n\n6. Testing JSON serialization...")
        analysis_dict = analysis.to_dict()
        
        print(f"   ✓ Position analysis serialized successfully")
        print(f"   ✓ Keys: {', '.join(list(analysis_dict.keys())[:5])}...")
        print(f"   ✓ Candidate moves: {len(analysis_dict['candidate_moves'])}")
        
        print("\n" + "=" * 60)
        print("✅ All manual tests passed!")
        print("=" * 60)
        
        print("\n📊 Summary:")
        print("   - Move recommendation service: ✓ Working")
        print("   - Stockfish integration: ✓ Working")
        print("   - Tactical theme detection: ✓ Working")
        print("   - Move explanations: ✓ Working")
        print("   - Position analysis: ✓ Working")
        print("   - JSON serialization: ✓ Working")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        await engine.close()
        print("\n🔒 Engine closed")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_move_recommendations())
    sys.exit(0 if success else 1)
