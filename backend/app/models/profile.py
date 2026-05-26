from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    JSON,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class PlayerProfile(Base):
    """Versioned longitudinal player profile snapshot.

    Each row is an immutable point-in-time aggregate for long-term coaching
    memory. Downstream consumers:
    - Profile builder (P1-PP-01): inserts new snapshots after aggregation
    - Coach context assembler (P3-CM-*): reads latest snapshot per user
    - Frontend profile card: trend sparklines across snapshot history
    """

    __tablename__ = "player_profiles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "profile_version",
            name="uq_player_profiles_user_version",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    profile_version = Column(Integer, nullable=False)
    snapshot_at = Column(DateTime(timezone=True), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)

    archetype = Column(Text, nullable=True)
    primary_strengths = Column(JSON, nullable=True)
    primary_weaknesses = Column(JSON, nullable=True)
    style_indicators = Column(JSON, nullable=True)
    time_management_profile = Column(JSON, nullable=True)
    phase_performance = Column(JSON, nullable=True)
    opening_repertoire = Column(JSON, nullable=True)
    tactical_themes = Column(JSON, nullable=True)
    pattern_summary_refs = Column(JSON, nullable=True)
    rating_trends = Column(JSON, nullable=True)

    games_analyzed_count = Column(Integer, nullable=False, default=0)
    patterns_detected_count = Column(Integer, nullable=False, default=0)
    first_game_date = Column(DateTime(timezone=True), nullable=True)
    profile_summary = Column(Text, nullable=True)

    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="profiles")

    def __repr__(self) -> str:
        return (
            f"<PlayerProfile(id={self.id}, user_id={self.user_id}, "
            f"version={self.profile_version}, snapshot_at={self.snapshot_at})>"
        )
