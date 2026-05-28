"""Domain types for the pattern recognition pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PatternSeverity(str, Enum):
    """Human-readable severity stored on ``PlayerPattern.severity``."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PatternOccurrenceInput:
    """Single detection event before persistence."""

    game_id: int
    move_number: int = 0
    game_phase: Optional[str] = None
    fen_before: Optional[str] = None
    fen_after: Optional[str] = None
    user_move: Optional[str] = None
    best_move: Optional[str] = None
    user_eval: Optional[float] = None
    best_eval: Optional[float] = None
    eval_delta: Optional[float] = None
    context_description: Optional[str] = None
    detector_metadata: Optional[Dict[str, Any]] = None


@dataclass
class DetectedPattern:
    """In-memory pattern aggregate produced by deterministic detectors."""

    pattern_type: str
    pattern_subtype: str
    severity: PatternSeverity
    confidence_score: float
    occurrence_count: int
    affected_games_count: int
    affected_games_ratio: float
    pattern_description: str
    example_positions: List[Dict[str, Any]] = field(default_factory=list)
    occurrences: List[PatternOccurrenceInput] = field(default_factory=list)
    is_strength: bool = False
    recommended_drill_type: Optional[str] = None
    trend_direction: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def pattern_key(self) -> tuple[str, str]:
        return (self.pattern_type, self.pattern_subtype)


@dataclass
class PatternAggregationInput:
    """Stockfish-grounded aggregates built from persisted ``GameAnalysis`` rows."""

    user_id: int
    total_analyzed_games: int
    opening_acpls: List[float]
    middlegame_acpls: List[float]
    endgame_acpls: List[float]
    opening_by_game: List[Dict[str, Any]]
    """Per-game opening stats: game_id, opening_name, opening_eco, opening_acpl."""

    @property
    def opening_performance(self) -> Dict[str, Any]:
        acpls = self.opening_acpls
        return {
            "acpl": sum(acpls) / len(acpls) if acpls else 0.0,
            "games_count": len(acpls),
        }

    @property
    def middlegame_performance(self) -> Dict[str, Any]:
        acpls = self.middlegame_acpls
        return {
            "acpl": sum(acpls) / len(acpls) if acpls else 0.0,
            "games_count": len(acpls),
        }

    @property
    def endgame_performance(self) -> Dict[str, Any]:
        acpls = self.endgame_acpls
        return {
            "acpl": sum(acpls) / len(acpls) if acpls else 0.0,
            "games_count": len(acpls),
        }


@dataclass
class PatternRunResult:
    """Output of a full pattern detection run (pre-persistence snapshot)."""

    user_id: int
    patterns: List[DetectedPattern]
    games_considered: int
    ran_at: datetime = field(default_factory=lambda: datetime.utcnow())
    detector_version: str = "pattern_engine_v1"

    @property
    def pattern_count(self) -> int:
        return len(self.patterns)
