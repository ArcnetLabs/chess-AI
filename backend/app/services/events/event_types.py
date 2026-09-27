"""Chess event vocabulary, severity bands and concept mapping.

Code-owned and versioned. Detectors may only emit these values, and the LLM may
never introduce one: a pattern built on an event has to be reproducible from
stored rows (see ``docs/architecture/PLAYER_INTELLIGENCE_ARCHITECTURE.md`` §4).
"""

from __future__ import annotations

from typing import Dict

# Bump when a detector's rules change, so stored events remain interpretable.
EVENT_DETECTOR_VERSION = 1

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------
EVENT_MAJOR_BLUNDER = "major_blunder"
EVENT_TACTICAL_MISS = "tactical_miss"
EVENT_MISSED_WIN = "missed_win"
EVENT_CONVERSION_FAILURE = "conversion_failure"
EVENT_ENDGAME_TECHNIQUE_FAILURE = "endgame_technique_failure"
EVENT_KING_SAFETY_ERROR = "king_safety_error"
EVENT_PIECE_ACTIVITY_ERROR = "piece_activity_error"
EVENT_STRUCTURE_ERROR = "pawn_structure_error"
EVENT_EXCHANGE_ERROR = "exchange_error"
EVENT_THREAT_UNANSWERED = "threat_unanswered"
EVENT_FAILED_TO_PUNISH = "failed_to_punish"
EVENT_OPENING_DEVIATION = "opening_deviation"
EVENT_PAWN_STRUCTURE_WEAKENING = "premature_pawn_push"
EVENT_TIME_PRESSURE_ERROR = "time_pressure_error"  # requires clock data; not emitted yet

EVENT_TYPES = (
    EVENT_MAJOR_BLUNDER,
    EVENT_TACTICAL_MISS,
    EVENT_MISSED_WIN,
    EVENT_CONVERSION_FAILURE,
    EVENT_ENDGAME_TECHNIQUE_FAILURE,
    EVENT_KING_SAFETY_ERROR,
    EVENT_PIECE_ACTIVITY_ERROR,
    EVENT_STRUCTURE_ERROR,
    EVENT_EXCHANGE_ERROR,
    EVENT_THREAT_UNANSWERED,
    EVENT_FAILED_TO_PUNISH,
    EVENT_OPENING_DEVIATION,
    EVENT_PAWN_STRUCTURE_WEAKENING,
    EVENT_TIME_PRESSURE_ERROR,
)

# ---------------------------------------------------------------------------
# Concepts — the chess idea an event embodies. Recommendations are built from
# concepts, not from event labels, so this mapping is the join between
# "what went wrong" and "what to teach".
# ---------------------------------------------------------------------------
CONCEPT_TACTICS = "tactics"
CONCEPT_CALCULATION = "calculation"
CONCEPT_KING_SAFETY = "king_safety"
CONCEPT_PIECE_ACTIVITY = "piece_activity"
CONCEPT_PAWN_STRUCTURE = "pawn_structure"
CONCEPT_ENDGAME_TECHNIQUE = "endgame_technique"
CONCEPT_CONVERSION = "conversion"
CONCEPT_OPENING = "opening"
CONCEPT_EXCHANGES = "exchanges"
CONCEPT_THREAT_AWARENESS = "threat_awareness"
CONCEPT_TIME_MANAGEMENT = "time_management"

EVENT_CONCEPTS: Dict[str, str] = {
    EVENT_MAJOR_BLUNDER: CONCEPT_CALCULATION,
    EVENT_TACTICAL_MISS: CONCEPT_TACTICS,
    EVENT_MISSED_WIN: CONCEPT_CONVERSION,
    EVENT_CONVERSION_FAILURE: CONCEPT_CONVERSION,
    EVENT_ENDGAME_TECHNIQUE_FAILURE: CONCEPT_ENDGAME_TECHNIQUE,
    EVENT_KING_SAFETY_ERROR: CONCEPT_KING_SAFETY,
    EVENT_PIECE_ACTIVITY_ERROR: CONCEPT_PIECE_ACTIVITY,
    EVENT_STRUCTURE_ERROR: CONCEPT_PAWN_STRUCTURE,
    EVENT_EXCHANGE_ERROR: CONCEPT_EXCHANGES,
    EVENT_THREAT_UNANSWERED: CONCEPT_THREAT_AWARENESS,
    EVENT_FAILED_TO_PUNISH: CONCEPT_THREAT_AWARENESS,
    EVENT_OPENING_DEVIATION: CONCEPT_OPENING,
    EVENT_PAWN_STRUCTURE_WEAKENING: CONCEPT_PAWN_STRUCTURE,
    EVENT_TIME_PRESSURE_ERROR: CONCEPT_TIME_MANAGEMENT,
}

# ---------------------------------------------------------------------------
# Severity — a function of eval damage, never a hand-set label.
# ---------------------------------------------------------------------------
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"

SEVERITY_ORDER = (SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL)


def severity_for_cp_loss(cp_loss: float) -> str:
    """Band a centipawn loss. Thresholds match the move-classification ladder."""
    if cp_loss >= 500:
        return SEVERITY_CRITICAL
    if cp_loss >= 300:
        return SEVERITY_HIGH
    if cp_loss >= 150:
        return SEVERITY_MEDIUM
    return SEVERITY_LOW


def concept_for(event_type: str) -> str:
    """Concept behind an event type; unknown types fall back to calculation."""
    return EVENT_CONCEPTS.get(event_type, CONCEPT_CALCULATION)


# ---------------------------------------------------------------------------
# Detection thresholds (single place, so detectors stay comparable)
# ---------------------------------------------------------------------------
BLUNDER_CP_LOSS = 300.0  # a real blunder
SIGNIFICANT_CP_LOSS = 150.0  # worth coaching about
WINNING_EVAL = 200.0  # "was winning" threshold
CLEAR_ADVANTAGE = 150.0
OPPONENT_ERROR_CP_LOSS = 150.0  # opponent's move was itself a mistake
