"""
Coaching services for chess improvement.

Provides recommendation engine, move analysis, and coaching chatbot functionality.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class RecommendationCategory(str, Enum):
    """Categories for coaching recommendations."""
    TACTICS = "tactics"
    ENDGAME = "endgame"
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    TIME_MANAGEMENT = "time_management"
    CALCULATION = "calculation"
    VISUALIZATION = "visualization"
    PATTERN_RECOGNITION = "pattern_recognition"
    TECHNIQUE = "technique"
    STRATEGY = "strategy"


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PatternMatch:
    """Represents a detected pattern in user's play."""
    pattern_name: str
    severity: float  # 0-1 scale
    frequency: int  # Number of occurrences
    evidence: Dict[str, Any]  # Supporting data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern_name": self.pattern_name,
            "severity": self.severity,
            "frequency": self.frequency,
            "evidence": self.evidence
        }


@dataclass
class Recommendation:
    """Represents a coaching recommendation."""
    category: str
    priority: str
    priority_score: float  # 0-100
    title: str
    description: str
    actionable_steps: List[str] = field(default_factory=list)
    related_games: Optional[List[int]] = None
    resources: Optional[List[str]] = None
    pattern_match: Optional[PatternMatch] = None
    pattern_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "category": self.category,
            "priority": self.priority,
            "priority_score": self.priority_score,
            "title": self.title,
            "description": self.description,
            "actionable_steps": self.actionable_steps
        }

        if self.pattern_id is not None:
            result["pattern_id"] = self.pattern_id
        
        if self.related_games:
            result["related_games"] = self.related_games
        
        if self.resources:
            result["resources"] = self.resources
            
        if self.pattern_match:
            result["pattern_match"] = self.pattern_match.to_dict()
        
        return result


__all__ = [
    "RecommendationCategory",
    "RecommendationPriority",
    "PatternMatch",
    "Recommendation"
]
