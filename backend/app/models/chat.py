"""Durable coaching conversation records."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChatSessionRecord(Base):
    """Postgres source of truth for a coaching conversation."""

    __tablename__ = "chat_sessions"

    session_id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    context_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="chat_sessions")

    __table_args__ = (
        Index("idx_chat_sessions_user_updated", "user_id", "updated_at"),
    )
