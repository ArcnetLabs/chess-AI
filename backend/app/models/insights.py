from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class UserInsight(Base):
    """User insights model for storing analysis summaries and recommendations."""
    
    __tablename__ = "user_insights"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Analysis period
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    analysis_type = Column(String, default="weekly")  # weekly, monthly, custom
    
    # Games included in analysis
    total_games = Column(Integer, default=0)
    games_analyzed = Column(Integer, default=0)
    
    # Performance metrics
    average_acpl = Column(Float)
    performance_trend = Column(String)  # improving, declining, stable
    rating_change = Column(Integer)  # Net rating change in period
    
    # Game phase performance
    opening_performance = Column(JSON)  # {acpl: float, common_mistakes: [...]}
    middlegame_performance = Column(JSON)
    endgame_performance = Column(JSON)
    
    # Move quality distribution
    move_quality_stats = Column(JSON)  # {brilliant: 5, great: 10, ...}
    
    # Common issues and patterns
    frequent_mistakes = Column(JSON)  # [{pattern: "hanging pieces", count: 5, severity: "high"}]
    opening_repertoire = Column(JSON)  # Opening statistics and recommendations
    time_management = Column(JSON)  # Time usage patterns
    
    # Improvement recommendations
    recommendations = Column(JSON)  # [{category: "tactics", priority: "high", description: "..."}]
    focus_areas = Column(JSON)  # Areas needing most attention
    
    # Enhanced recommendations (Phase 1)
    recommendation_scores = Column(JSON)  # Priority scores for each recommendation
    focus_areas_detailed = Column(JSON)  # Granular weakness breakdown
    pattern_matches = Column(JSON)  # Detected patterns with evidence
    
    # Progress tracking
    improvement_metrics = Column(JSON)  # Comparison with previous periods
    goals_progress = Column(JSON)  # User-set goals and progress
    
    # Report generation
    report_generated = Column(Boolean, default=False)
    report_path = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="insights")
    
    def __repr__(self):
        return f"<UserInsight(user_id={self.user_id}, period={self.analysis_type}, acpl={self.average_acpl})>"
