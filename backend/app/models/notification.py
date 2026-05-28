"""In-app user notification feed (P3-PC-02)."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class UserNotification(Base):
    """Per-user in-app notification row."""

    __tablename__ = "user_notifications"
    __table_args__ = (
        Index("idx_user_notifications_user_created", "user_id", "created_at"),
        Index("idx_user_notifications_user_read_at", "user_id", "read_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notification_type = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="notifications")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __repr__(self) -> str:
        return (
            f"<UserNotification(id={self.id}, user_id={self.user_id}, "
            f"type={self.notification_type!r}, read={self.is_read})>"
        )
