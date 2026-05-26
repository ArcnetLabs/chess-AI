"""API endpoints for chess coaching chatbot.

All mutating endpoints require a Supabase session. Session-level
ownership is currently scoped to "any authenticated user can touch any
chat session" because sessions are in-memory and identified by UUID — a
follow-up pass (tracked under the analysis-pipeline remediation) will
persist sessions per ``current_user.id`` and add per-session ownership
checks.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from loguru import logger

from ..middleware.auth_middleware import get_current_user
from ..models import User
from ..services.chat.chess_coach import ChessCoach
from ..services.engine.engine_pool import check_engine_health


router = APIRouter(tags=["chat"])


# Request/Response Models
class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    message: str = Field(..., min_length=1, description="User's message")
    session_id: Optional[str] = Field(None, description="Chat session ID")
    user_id: Optional[int] = Field(None, description="User ID for personalization")
    position_fen: Optional[str] = Field(None, description="Current chess position (FEN)")


class CreateSessionRequest(BaseModel):
    """Request model for creating a chat session."""
    user_id: Optional[int] = Field(None, description="User ID")


class ChatMessageResponse(BaseModel):
    """Response model for chat messages."""
    success: bool
    session_id: str
    response: dict
    context: Optional[dict] = None


# Dependency for chess coach
_coach_instance: Optional[ChessCoach] = None


async def get_chess_coach() -> ChessCoach:
    """Get chess coach instance (singleton; engine acquired lazily via pool)."""
    global _coach_instance

    if _coach_instance is None:
        try:
            logger.info("Initializing Chess Coach...")
            _coach_instance = ChessCoach()
            logger.info("Chess Coach initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chess Coach: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Chess coach initialization failed: {str(e)}"
            )

    return _coach_instance


@router.post("/message", summary="Send a message to the chess coach")
async def send_message(
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
) -> ChatMessageResponse:
    """
    Send a message to the chess coach and get a response.
    
    The coach will:
    - Analyze positions when asked
    - Explain specific moves
    - Compare different moves
    - Answer general chess questions
    - Maintain conversation context
    
    Returns:
    - Conversational response
    - Analysis data (if applicable)
    - Suggestions for follow-up questions
    """
    try:
        logger.info(f"Processing message: {request.message[:50]}...")
        # Trust the authenticated identity, not the request body.
        effective_user_id = current_user.id

        response = await coach.process_message(
            message=request.message,
            session_id=request.session_id,
            user_id=effective_user_id,
            position_fen=request.position_fen
        )
        
        # Get session context
        session = coach.get_session(response.position_fen or request.session_id or "")
        
        return ChatMessageResponse(
            success=True,
            session_id=session.session_id if session else "unknown",
            response=response.to_dict(),
            context=session.to_dict() if session else None
        )
        
    except Exception as e:
        logger.error(f"Chat message processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post("/session", summary="Create a new chat session")
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
):
    """
    Create a new chat session.
    
    Returns:
    - Session ID
    - Welcome message
    """
    try:
        # Always create sessions under the authenticated user identity.
        session = coach.create_session(user_id=current_user.id)
        
        welcome_message = """Hi! I'm your AI chess coach. I can help you with:

🔍 **Position Analysis** - "Analyze this position" or "What's the best move?"
📚 **Move Explanations** - "Why is Nf3 good?" or "Explain e4"
⚖️ **Move Comparisons** - "Compare e4 and d4"
💡 **General Advice** - "How do I improve my tactics?"

What would you like to work on today?"""
        
        return {
            "success": True,
            "session_id": session.session_id,
            "message": welcome_message,
            "context": session.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/session/{session_id}", summary="Get chat session details")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
):
    """
    Get details of a chat session.
    
    Returns:
    - Session context
    - Conversation history
    - Current position
    """
    session = coach.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    return {
        "success": True,
        "session": session.to_dict()
    }


@router.delete("/session/{session_id}", summary="Delete a chat session")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
):
    """
    Delete a chat session and its history.
    
    Returns:
    - Success status
    """
    deleted = coach.delete_session(session_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    return {
        "success": True,
        "message": f"Session {session_id} deleted"
    }


@router.get("/session/{session_id}/history", summary="Get conversation history")
async def get_history(
    session_id: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
):
    """
    Get conversation history for a session.
    
    Args:
        session_id: Session ID
        limit: Maximum number of messages to return
    
    Returns:
    - List of messages
    """
    session = coach.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    recent_messages = session.get_recent_messages(limit)
    
    return {
        "success": True,
        "session_id": session_id,
        "messages": [msg.to_dict() for msg in recent_messages],
        "total_messages": len(session.conversation_history)
    }


@router.get("/health", summary="Check chatbot service health")
async def health_check():
    """Check if chatbot service is working."""
    try:
        coach = await get_chess_coach()
        stockfish_health = await check_engine_health()
        engine_status = "available" if stockfish_health.get("available") else "unavailable"

        return {
            "status": "healthy" if engine_status == "available" else "degraded",
            "service": "chess-coach-chatbot",
            "stockfish": engine_status,
            "active_sessions": len(coach.sessions),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "chess-coach-chatbot",
            "error": str(e)
        }


@router.post("/quick-analysis", summary="Quick position analysis (no session)")
async def quick_analysis(
    position_fen: str,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
):
    """
    Quick position analysis without creating a session.
    
    Useful for one-off position checks.
    """
    try:
        response = await coach.process_message(
            message="Analyze this position",
            position_fen=position_fen
        )
        
        return {
            "success": True,
            "response": response.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Quick analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )
