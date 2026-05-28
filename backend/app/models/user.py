from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class User(Base):
    """Local user record.

    Identity is owned by Supabase Auth — ``supabase_user_id`` is the
    canonical foreign key into the Supabase ``auth.users`` table. Local
    rows are auto-provisioned on first authenticated request (see
    :mod:`app.middleware.auth_middleware`).

    ``chesscom_username`` is linked profile data, not identity. It is
    nullable for users who sign up via Supabase but have not yet linked
    a Chess.com account.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Supabase identity (canonical). UUIDv4 stored as VARCHAR(36) so the
    # column is portable between Postgres (production) and SQLite (dev
    # fallback). See migration 0005.
    supabase_user_id = Column(String(36), unique=True, index=True, nullable=True)

    # Chess.com linked profile data. Optional until the user completes the
    # /onboarding/link-chesscom flow.
    chesscom_username = Column(String, unique=True, index=True, nullable=True)
    display_name = Column(String)
    email = Column(String, unique=True, index=True, nullable=True)

    # Authentication and connection status
    connection_type = Column(String, default="username_only")  # "username_only", "oauth", "api_key"
    is_chesscom_connected = Column(Boolean, default=False)
    chesscom_user_id = Column(String, nullable=True)  # Official Chess.com user ID when authenticated
    access_token = Column(Text, nullable=True)  # OAuth token (encrypted)
    refresh_token = Column(Text, nullable=True)  # OAuth refresh token (encrypted)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Chess.com profile data
    chesscom_profile = Column(JSON, nullable=True)
    current_ratings = Column(JSON, nullable=True)  # Store different time control ratings
    
    # User preferences
    analysis_preferences = Column(JSON, default={})
    notification_preferences = Column(JSON, default={})
    
    # Subscription tier management
    tier = Column(String, default="free")  # "free" or "pro"
    ai_analyses_used = Column(Integer, default=0)
    ai_analyses_limit = Column(Integer, default=5)  # Free tier gets 5 AI analyses
    trial_exhausted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Game statistics
    total_games = Column(Integer, default=0)
    analyzed_games = Column(Integer, default=0)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_analysis_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    games = relationship("Game", back_populates="user", cascade="all, delete-orphan")
    insights = relationship("UserInsight", back_populates="user", cascade="all, delete-orphan")
    patterns = relationship(
        "PlayerPattern", back_populates="user", cascade="all, delete-orphan"
    )
    pattern_occurrences = relationship(
        "PatternOccurrence", back_populates="user", cascade="all, delete-orphan"
    )
    profiles = relationship(
        "PlayerProfile", back_populates="user", cascade="all, delete-orphan"
    )
    semantic_memories = relationship(
        "SemanticMemory", back_populates="user", cascade="all, delete-orphan"
    )
    training_plans = relationship(
        "TrainingPlan", back_populates="user", cascade="all, delete-orphan"
    )
    drill_attempts = relationship(
        "DrillAttempt", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_authenticated(self) -> bool:
        """Check if user has authenticated Chess.com connection."""
        return self.connection_type in ["oauth", "api_key"] and self.is_chesscom_connected
    
    @property
    def connection_status(self) -> str:
        """Get user-friendly connection status."""
        if self.connection_type == "username_only":
            return "Public Data Only"
        elif self.connection_type == "oauth" and self.is_chesscom_connected:
            return "Authenticated"
        elif self.connection_type == "api_key" and self.is_chesscom_connected:
            return "API Connected"
        else:
            return "Disconnected"
    
    @property
    def can_access_private_data(self) -> bool:
        """Check if user can access private Chess.com data."""
        return self.is_authenticated
    
    @property
    def is_pro(self) -> bool:
        """Check if user has Pro subscription."""
        return self.tier == "pro"
    
    @property
    def can_use_ai_analysis(self) -> bool:
        """Check if user can use AI-powered analysis."""
        if self.is_pro:
            return True
        # Free users get limited AI analyses
        return self.ai_analyses_used < self.ai_analyses_limit
    
    @property
    def remaining_ai_analyses(self) -> int:
        """Get remaining AI analysis count for free users."""
        if self.is_pro:
            return -1  # Unlimited
        return max(0, self.ai_analyses_limit - self.ai_analyses_used)
    
    def increment_ai_usage(self):
        """Increment AI analysis usage counter."""
        if not self.is_pro:
            self.ai_analyses_used += 1
            if self.ai_analyses_used >= self.ai_analyses_limit and not self.trial_exhausted_at:
                from datetime import datetime, timezone
                self.trial_exhausted_at = datetime.now(timezone.utc)
    
    def __repr__(self):
        return (
            f"<User(id={self.id}, supabase_user_id='{self.supabase_user_id}', "
            f"chesscom_username='{self.chesscom_username}', tier='{self.tier}')>"
        )
