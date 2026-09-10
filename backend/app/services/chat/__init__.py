"""Chess coaching chatbot services."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ChatIntent(str, Enum):
    """Intent classification for chat messages."""
    ANALYZE_POSITION = "analyze_position"
    ANALYZE_GAME = "analyze_game"
    EXPLAIN_MOVE = "explain_move"
    COMPARE_MOVES = "compare_moves"
    GENERAL_QUESTION = "general_question"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


class MessageRole(str, Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SessionMode(str, Enum):
    """Conversation mode for a chat session.

    ``coach`` and ``analyze`` use the standard coaching prompt; ``interview``
    runs the structured intake that extracts the player's goals and writes
    them into the memory layer.
    """
    COACH = "coach"
    ANALYZE = "analyze"
    INTERVIEW = "interview"


@dataclass
class ChatMessage:
    """Represents a chat message."""
    
    role: MessageRole
    content: str
    position_fen: Optional[str] = None
    intent: Optional[ChatIntent] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "role": self.role.value,
            "content": self.content,
            "position_fen": self.position_fen,
            "intent": self.intent.value if self.intent else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata or {}
        }


@dataclass
class ChatContext:
    """Context for a chat session."""
    
    session_id: str
    user_id: Optional[int] = None
    current_position: Optional[str] = None
    conversation_history: List[ChatMessage] = None
    skill_level: str = "intermediate"
    focus_areas: List[str] = None
    recent_topics: List[str] = None
    # Rolling summary of everything that has scrolled out of the recent
    # window, maintained by the chat-memory Celery task (user directive:
    # summarize context instead of silently cutting it).
    early_summary: str = ""
    summary_upto: int = 0
    # Conversation mode (coach | analyze | interview). Interview sessions
    # run the structured intake prompt; see chess_coach._llm_coach_reply.
    mode: str = SessionMode.COACH.value
    # Compact goal summary emitted by the coach at the end of an interview
    # (Goal / Weaknesses / Time budget / Openings). Persisted into the
    # coaching memory slice by the chat-memory task.
    interview_summary: str = ""
    # When set, the session is scoped to one analyzed game: every coach call
    # grounds on that game's persisted Stockfish analysis (game chat).
    game_id: Optional[int] = None

    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.focus_areas is None:
            self.focus_areas = []
        if self.recent_topics is None:
            self.recent_topics = []
        try:
            SessionMode(self.mode)
        except ValueError:
            raise ValueError(
                f"Unknown session mode: {self.mode!r} "
                f"(expected one of {[m.value for m in SessionMode]})"
            )
    
    def add_message(self, message: ChatMessage):
        """Add a message to conversation history."""
        self.conversation_history.append(message)
    
    def get_recent_messages(self, n: int = 5) -> List[ChatMessage]:
        """Get the N most recent messages."""
        return self.conversation_history[-n:] if self.conversation_history else []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "current_position": self.current_position,
            "conversation_history": [msg.to_dict() for msg in self.conversation_history],
            "skill_level": self.skill_level,
            "focus_areas": self.focus_areas,
            "recent_topics": self.recent_topics,
            "early_summary": self.early_summary,
            "summary_upto": self.summary_upto,
            "mode": self.mode,
            "interview_summary": self.interview_summary,
            "game_id": self.game_id,
        }


@dataclass
class ChatResponse:
    """Response from the chess coach."""
    
    message: str
    intent: ChatIntent
    analysis: Optional[Dict[str, Any]] = None
    suggestions: List[str] = None
    position_fen: Optional[str] = None
    session_id: Optional[str] = None
    cited_pattern_ids: Optional[List[int]] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    used_llm: bool = False
    retrieval_used: bool = False
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    llm_latency_ms: Optional[int] = None
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []
        if self.cited_pattern_ids is None:
            self.cited_pattern_ids = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "message": self.message,
            "intent": self.intent.value,
            "analysis": self.analysis,
            "suggestions": self.suggestions,
            "position_fen": self.position_fen,
            "session_id": self.session_id,
            "cited_pattern_ids": self.cited_pattern_ids or [],
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "used_llm": self.used_llm,
            "retrieval_used": self.retrieval_used,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "llm_latency_ms": self.llm_latency_ms,
        }
