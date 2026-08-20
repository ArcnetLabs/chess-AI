"""Authenticated API endpoints for persistent chess coaching sessions.

Chat sessions are stored in PostgreSQL, cached in Redis when available, and
scoped to the authenticated user on every session-level operation.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from loguru import logger

from sqlalchemy.orm import Session

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user
from ..models import User
from ..services.chat.chess_coach import ChessCoach
from ..services.engine.engine_pool import check_engine_health
from ..services.integration.ai_client import get_ai_client


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


def _require_owned_session(
    coach: ChessCoach, session_id: str, user_id: int, db: Session
):
    """Load a session and enforce the owner captured in its chat context."""
    session = coach.get_session(session_id, db=db)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="You do not have access to this session")
    return session


def _session_summary(session) -> dict:
    history = session.conversation_history
    latest = history[-1] if history else None
    preview = next(
        (message.content for message in reversed(history) if message.role.value == "user"),
        latest.content if latest else "New coaching conversation",
    )
    return {
        "session_id": session.session_id,
        "message_count": len(history),
        "preview": preview[:100],
        "updated_at": latest.timestamp.isoformat() if latest and latest.timestamp else None,
    }


# Dependency for chess coach
_coach_instance: Optional[ChessCoach] = None


async def get_chess_coach() -> ChessCoach:
    """Get chess coach instance (singleton; engine acquired lazily via pool)."""
    global _coach_instance

    if _coach_instance is None:
        try:
            logger.info("Initializing Chess Coach...")
            ai_client = None
            try:
                ai_client = get_ai_client()
            except Exception as ai_exc:
                logger.warning(
                    f"AI client unavailable; coach will use template fallback: {ai_exc}"
                )
            _coach_instance = ChessCoach(ai_client=ai_client)
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
    db: Session = Depends(get_db),
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
        if request.session_id:
            _require_owned_session(
                coach, request.session_id, effective_user_id, db
            )

        response = await coach.process_message(
            message=request.message,
            session_id=request.session_id,
            user_id=effective_user_id,
            position_fen=request.position_fen,
            db=db,
        )
        
        # Get session context
        effective_session_id = response.session_id or request.session_id
        session = (
            coach.get_session(effective_session_id, db=db)
            if effective_session_id
            else None
        )

        return ChatMessageResponse(
            success=True,
            session_id=effective_session_id or (session.session_id if session else "unknown"),
            response=response.to_dict(),
            context=session.to_dict() if session else None
        )
        
    except HTTPException:
        raise
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
    db: Session = Depends(get_db),
):
    """
    Create a new chat session.
    
    Returns:
    - Session ID
    - Welcome message
    """
    try:
        # Always create sessions under the authenticated user identity.
        session = coach.create_session(user_id=current_user.id, db=db)
        
        welcome_message = session.conversation_history[-1].content
        
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
    db: Session = Depends(get_db),
):
    """
    Get details of a chat session.
    
    Returns:
    - Session context
    - Conversation history
    - Current position
    """
    session = _require_owned_session(coach, session_id, current_user.id, db)
    
    return {
        "success": True,
        "session": session.to_dict()
    }


@router.delete("/session/{session_id}", summary="Delete a chat session")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
    db: Session = Depends(get_db),
):
    """
    Delete a chat session and its history.
    
    Returns:
    - Success status
    """
    _require_owned_session(coach, session_id, current_user.id, db)
    if not coach.delete_session(session_id, db=db):
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
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
    db: Session = Depends(get_db),
):
    """
    Get conversation history for a session.
    
    Args:
        session_id: Session ID
        limit: Maximum number of messages to return
    
    Returns:
    - List of messages
    """
    session = _require_owned_session(coach, session_id, current_user.id, db)
    
    recent_messages = session.get_recent_messages(max(1, min(limit, 500)))
    
    return {
        "success": True,
        "session_id": session_id,
        "messages": [msg.to_dict() for msg in recent_messages],
        "total_messages": len(session.conversation_history)
    }


@router.get("/sessions", summary="List the current user's coaching conversations")
async def list_sessions(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    coach: ChessCoach = Depends(get_chess_coach),
    db: Session = Depends(get_db),
):
    sessions = coach.session_store.list_for_user(
        current_user.id, max(1, min(limit, 100)), db=db
    )
    return {"success": True, "sessions": [_session_summary(session) for session in sessions]}


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
            "active_sessions": coach.session_store.active_session_count(),
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
            position_fen=position_fen,
            user_id=current_user.id,
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
