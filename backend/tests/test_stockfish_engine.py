"""Tests for Stockfish engine wrapper."""

import sys
from pathlib import Path

# Add parent directory to path for direct execution
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
import chess
from app.services.engine.stockfish_engine import StockfishEngine, StockfishEngineError


@pytest.mark.asyncio
async def test_engine_initialization():
    """Test that engine initializes correctly."""
    engine = StockfishEngine()
    
    try:
        await engine.initialize()
        assert engine.is_initialized()
        assert engine.engine is not None
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_engine_auto_path_detection():
    """Test automatic Stockfish path detection."""
    engine = StockfishEngine(stockfish_path=None)
    
    # Should not raise error if Stockfish is installed
    try:
        await engine.initialize()
        assert engine.stockfish_path is not None
        assert len(engine.stockfish_path) > 0
    except StockfishEngineError as e:
        # Expected if Stockfish not installed
        assert "not found" in str(e).lower()
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_evaluate_starting_position():
    """Test evaluation of starting chess position."""
    engine = StockfishEngine(depth=10)
    
    try:
        await engine.initialize()
        
        # Starting position
        board = chess.Board()
        result = await engine.evaluate_position(board)
        
        # Starting position should be roughly equal (around 0 centipawns)
        assert result is not None
        assert "evaluation_cp" in result
        assert "best_move" in result
        assert result["best_move"] is not None
        
        # Evaluation should be close to 0 (within 50 centipawns)
        if result["evaluation_cp"] is not None:
            assert abs(result["evaluation_cp"]) < 100
        
        print(f"Starting position evaluation: {result}")
        
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_evaluate_tactical_position():
    """Test evaluation of a tactical position with clear best move."""
    engine = StockfishEngine(depth=15)
    
    try:
        await engine.initialize()
        
        # Position with a forced checkmate in 1 (Scholar's mate setup)
        # After 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6 4.Qxf7#
        board = chess.Board("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
        
        result = await engine.evaluate_position(board)
        
        assert result is not None
        assert result["is_mate"] == True
        assert result["mate_in"] is not None
        
        print(f"Checkmate position evaluation: {result}")
        
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_get_best_move():
    """Test getting best move for a position."""
    engine = StockfishEngine(depth=10)
    
    try:
        await engine.initialize()
        
        board = chess.Board()
        best_move = await engine.get_best_move(board)
        
        assert best_move is not None
        assert len(best_move) >= 4  # UCI format like "e2e4"
        
        # Verify it's a legal move
        move = chess.Move.from_uci(best_move)
        assert move in board.legal_moves
        
        print(f"Best move from starting position: {best_move}")
        
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_analyze_multiple_moves():
    """Test analyzing multiple candidate moves."""
    engine = StockfishEngine(depth=10)
    
    try:
        await engine.initialize()
        
        board = chess.Board()
        
        # Analyze common opening moves
        moves = [
            chess.Move.from_uci("e2e4"),  # King's pawn
            chess.Move.from_uci("d2d4"),  # Queen's pawn
            chess.Move.from_uci("g1f3"),  # Knight to f3
        ]
        
        results = await engine.analyze_moves(board, moves)
        
        assert len(results) == 3
        for result in results:
            assert "evaluation_cp" in result
            assert "move" in result
        
        print(f"Move analysis results: {results}")
        
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_context_manager():
    """Test using engine as async context manager."""
    async with StockfishEngine(depth=10) as engine:
        assert engine.is_initialized()
        
        board = chess.Board()
        result = await engine.evaluate_position(board)
        
        assert result is not None
        assert "best_move" in result


@pytest.mark.asyncio
async def test_engine_configuration():
    """Test engine configuration options."""
    engine = StockfishEngine(
        depth=20,
        threads=4,
        hash_size=512,
        time_limit=2.0
    )
    
    assert engine.depth == 20
    assert engine.threads == 4
    assert engine.hash_size == 512
    assert engine.time_limit == 2.0
    
    try:
        await engine.initialize()
        assert engine.is_initialized()
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_invalid_stockfish_path():
    """Test error handling for invalid Stockfish path."""
    engine = StockfishEngine(stockfish_path="/invalid/path/to/stockfish")
    
    with pytest.raises(StockfishEngineError):
        await engine.initialize()


@pytest.mark.asyncio
async def test_engine_reinitialization():
    """Test that reinitializing doesn't cause issues."""
    engine = StockfishEngine(depth=10)
    
    try:
        await engine.initialize()
        assert engine.is_initialized()
        
        # Initialize again
        await engine.initialize()
        assert engine.is_initialized()
        
        # Should still work
        board = chess.Board()
        result = await engine.evaluate_position(board)
        assert result is not None
        
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_evaluation_with_custom_depth():
    """Test evaluation with custom depth parameter."""
    engine = StockfishEngine(depth=10)
    
    try:
        await engine.initialize()
        
        board = chess.Board()
        
        # Evaluate with different depths
        result_shallow = await engine.evaluate_position(board, depth=5)
        result_deep = await engine.evaluate_position(board, depth=20)
        
        assert result_shallow is not None
        assert result_deep is not None
        
        # Both should have evaluations
        assert "evaluation_cp" in result_shallow
        assert "evaluation_cp" in result_deep
        
        print(f"Shallow (depth 5): {result_shallow}")
        print(f"Deep (depth 20): {result_deep}")
        
    finally:
        await engine.close()


if __name__ == "__main__":
    import asyncio
    
    async def run_basic_test():
        """Run a basic test to verify Stockfish is working."""
        print("Testing Stockfish engine integration...")
        print("-" * 50)
        
        try:
            async with StockfishEngine() as engine:
                print(f"✓ Engine initialized at: {engine.stockfish_path}")
                
                board = chess.Board()
                print(f"✓ Analyzing starting position...")
                
                result = await engine.evaluate_position(board)
                print(f"✓ Evaluation: {result['evaluation_cp']} centipawns")
                print(f"✓ Best move: {result['best_move']}")
                print(f"✓ Principal variation: {' '.join(result['pv'][:5])}")
                
                print("\n" + "=" * 50)
                print("SUCCESS: Stockfish engine is working correctly!")
                print("=" * 50)
                
        except StockfishEngineError as e:
            print(f"\n✗ ERROR: {e}")
            print("\nPlease ensure Stockfish is installed:")
            print("1. Download from: https://stockfishchess.org/download/")
            print("2. Place in: backend/stockfish/stockfish.exe (Windows)")
            print("   or: backend/stockfish/stockfish (Linux/Mac)")
    
    asyncio.run(run_basic_test())
