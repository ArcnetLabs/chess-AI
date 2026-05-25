"""Quick test of game analysis with real PGN."""

import sys
from pathlib import Path
import asyncio

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.analysis.unified_analyzer import UnifiedChessAnalyzer


# Sample game PGN (Scholar's Mate)
SAMPLE_PGN = """[Event "Casual Game"]
[Site "?"]
[Date "2024.01.01"]
[Round "?"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""


async def test_game_analysis():
    """Test analyzing a complete game."""
    print("=" * 60)
    print("Testing Game Analysis with Stockfish")
    print("=" * 60)
    
    async with UnifiedChessAnalyzer() as analyzer:
        print("\n📊 Analyzing Scholar's Mate game...")
        print("-" * 60)
        
        result = await analyzer.analyze_game(
            pgn_string=SAMPLE_PGN,
            user_color="black",
            game_id="test_game_1"
        )
        
        if result:
            print(f"\n✅ Analysis Complete!")
            print(f"\n📈 Overall Metrics:")
            print(f"   • User Color: {result.user_color}")
            print(f"   • Total Moves: {result.total_moves}")
            print(f"   • ACPL: {result.user_acpl:.1f}")
            print(f"   • Accuracy: {result.accuracy_percentage:.1f}%")
            
            print(f"\n🎯 Move Quality:")
            print(f"   • Best Moves: {result.best_moves}")
            print(f"   • Good Moves: {result.good_moves}")
            print(f"   • Inaccuracies: {result.inaccuracies}")
            print(f"   • Mistakes: {result.mistakes}")
            print(f"   • Blunders: {result.blunders}")
            
            print(f"\n📊 Phase Analysis:")
            if result.opening_phase:
                print(f"   • Opening ACPL: {result.opening_phase.average_acpl:.1f}")
            if result.middlegame_phase:
                print(f"   • Middlegame ACPL: {result.middlegame_phase.average_acpl:.1f}")
            if result.endgame_phase:
                print(f"   • Endgame ACPL: {result.endgame_phase.average_acpl:.1f}")
            
            print(f"\n⚠️ Critical Positions: {len(result.critical_positions)}")
            
            print(f"\n⏱️ Analysis Time: {result.analysis_time_seconds:.2f}s")
            print(f"🔧 Engine: {result.engine_version} (depth {result.analysis_depth})")
            
            print("\n" + "=" * 60)
            print("✅ SUCCESS: Game analysis working perfectly!")
            print("=" * 60)
        else:
            print("\n❌ Analysis failed")


if __name__ == "__main__":
    asyncio.run(test_game_analysis())
