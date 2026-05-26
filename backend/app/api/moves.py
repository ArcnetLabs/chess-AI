"""API endpoints for move recommendations and position analysis.

All position-analysis endpoints require an authenticated Supabase user;
they don't carry user-scoped data themselves but they exercise the
Stockfish engine pool which is a finite shared resource. The ``/health``
endpoint stays public so deployment platforms can probe it without a JWT.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from loguru import logger

from ..middleware.auth_middleware import get_current_user
from ..models import User
from ..services.moves.move_recommender import MoveRecommender
from ..services.engine.stockfish_engine import StockfishEngine, StockfishEngineError


router = APIRouter(prefix="/moves", tags=["moves"])


# Request/Response Models
class AnalyzePositionRequest(BaseModel):
    """Request model for position analysis."""
    fen: str = Field(..., description="Position in FEN notation")
    num_moves: int = Field(5, ge=1, le=10, description="Number of candidate moves to analyze")
    depth: int = Field(18, ge=10, le=25, description="Stockfish search depth")


class CompareMoveRequest(BaseModel):
    """Request model for comparing moves."""
    fen: str = Field(..., description="Position in FEN notation")
    moves: List[str] = Field(..., min_items=2, max_items=5, description="Moves to compare (SAN or UCI)")
    depth: int = Field(18, ge=10, le=25, description="Analysis depth")


class ExplainMoveRequest(BaseModel):
    """Request model for move explanation."""
    fen: str = Field(..., description="Position in FEN notation")
    move: str = Field(..., description="Move to explain (SAN or UCI)")
    depth: int = Field(18, ge=10, le=25, description="Analysis depth")


# Dependency for move recommender
async def get_move_recommender() -> MoveRecommender:
    """Get move recommender instance."""
    engine = StockfishEngine(depth=18, threads=2)
    recommender = MoveRecommender(stockfish_engine=engine)
    try:
        yield recommender
    finally:
        await engine.close()


@router.post("/analyze", summary="Analyze position and get move recommendations")
async def analyze_position(
    request: AnalyzePositionRequest,
    current_user: User = Depends(get_current_user),
    recommender: MoveRecommender = Depends(get_move_recommender),
):
    """
    Analyze a chess position and return top move recommendations.
    
    Returns:
    - Position evaluation
    - Top N candidate moves with explanations
    - Tactical themes
    - Strategic insights
    """
    try:
        logger.info(f"Analyzing position: {request.fen[:50]}...")
        
        analysis = await recommender.analyze_position(
            fen=request.fen,
            num_moves=request.num_moves,
            depth=request.depth
        )
        
        return {
            "success": True,
            "analysis": analysis.to_dict()
        }
        
    except StockfishEngineError as e:
        logger.error(f"Stockfish error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chess engine error: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"Invalid FEN: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid position: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Position analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post("/compare", summary="Compare multiple moves")
async def compare_moves(
    request: CompareMoveRequest,
    current_user: User = Depends(get_current_user),
    recommender: MoveRecommender = Depends(get_move_recommender),
):
    """
    Compare multiple moves from the same position.
    
    Returns:
    - Evaluation for each move
    - Comparison explanation
    - Recommendation for best move
    """
    try:
        logger.info(f"Comparing {len(request.moves)} moves")
        
        comparison = await recommender.compare_moves(
            fen=request.fen,
            moves=request.moves,
            depth=request.depth
        )
        
        return {
            "success": True,
            "comparison": comparison
        }
        
    except StockfishEngineError as e:
        logger.error(f"Stockfish error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chess engine error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Move comparison failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Comparison failed: {str(e)}"
        )


@router.get("/best/{fen:path}", summary="Get best move for position")
async def get_best_move(
    fen: str,
    depth: int = 18,
    current_user: User = Depends(get_current_user),
    recommender: MoveRecommender = Depends(get_move_recommender),
):
    """
    Get the best move for a position.
    
    Returns:
    - Best move in SAN notation
    - Evaluation
    - Brief explanation
    """
    try:
        logger.info(f"Getting best move for position")
        
        # Analyze position with just 1 move
        analysis = await recommender.analyze_position(
            fen=fen,
            num_moves=1,
            depth=depth
        )
        
        if not analysis.candidate_moves:
            raise HTTPException(
                status_code=400,
                detail="No legal moves in this position"
            )
        
        best_move = analysis.candidate_moves[0]
        
        return {
            "success": True,
            "best_move": best_move.move,
            "uci": best_move.uci,
            "evaluation": best_move.evaluation,
            "explanation": best_move.explanation,
            "mate_in": best_move.mate_in
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Best move calculation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get best move: {str(e)}"
        )


@router.post("/explain", summary="Get detailed explanation for a move")
async def explain_move(
    request: ExplainMoveRequest,
    current_user: User = Depends(get_current_user),
    recommender: MoveRecommender = Depends(get_move_recommender),
):
    """
    Get a detailed explanation for a specific move.
    
    Returns:
    - Move evaluation
    - Tactical themes
    - Pros and cons
    - Sample variations
    - Difficulty level
    """
    try:
        logger.info(f"Explaining move: {request.move}")
        
        # Analyze position to get move details
        analysis = await recommender.analyze_position(
            fen=request.fen,
            num_moves=10,  # Analyze more moves to find the requested one
            depth=request.depth
        )
        
        # Find the requested move in candidates
        requested_move = None
        for candidate in analysis.candidate_moves:
            if candidate.move == request.move or candidate.uci == request.move:
                requested_move = candidate
                break
        
        if not requested_move:
            # Move not in top candidates, analyze it separately
            import chess
            board = chess.Board(request.fen)
            try:
                move = board.parse_san(request.move)
            except:
                try:
                    move = chess.Move.from_uci(request.move)
                except:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid move: {request.move}"
                    )
            
            # Create basic recommendation for this move
            temp_board = board.copy()
            temp_board.push(move)
            
            eval_result = await recommender.engine.evaluate_position(temp_board, depth=request.depth)
            evaluation = -eval_result["evaluation_cp"] / 100.0 if eval_result["evaluation_cp"] is not None else 0
            
            return {
                "success": True,
                "move": board.san(move),
                "uci": move.uci(),
                "evaluation": evaluation,
                "explanation": f"This move leads to an evaluation of {evaluation:+.2f}",
                "note": "Move not in top recommendations"
            }
        
        return {
            "success": True,
            "explanation": requested_move.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Move explanation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Explanation failed: {str(e)}"
        )


@router.get("/health", summary="Check move analysis service health")
async def health_check():
    """Check if move analysis service is working."""
    try:
        # Try to initialize engine
        engine = StockfishEngine()
        await engine.initialize()
        await engine.close()
        
        return {
            "status": "healthy",
            "service": "move-analysis",
            "stockfish": "available"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "move-analysis",
            "stockfish": "unavailable",
            "error": str(e)
        }
