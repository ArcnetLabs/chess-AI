"""Shared thresholds for deterministic pattern detection.

Aligned with ``RecommendationEngine`` defaults so coaching recommendations
and persisted patterns describe the same weaknesses (P1-RE-01 will link IDs).
"""

# Minimum analyzed games before phase-level patterns are emitted.
MIN_PHASE_SAMPLE_GAMES = 3

# Minimum games played in an opening before opening-specific patterns fire.
MIN_OPENING_SAMPLE_GAMES = 2

# Phase ACPL thresholds (centipawns) — match recommendation_engine.py
OPENING_ACPL_THRESHOLD = 30.0
MIDDLEGAME_ACPL_THRESHOLD = 35.0
ENDGAME_ACPL_THRESHOLD = 40.0

# Per-opening opening-phase ACPL (recurring leak in one repertoire line).
OPENING_SPECIFIC_ACPL_THRESHOLD = 50.0

# Severity bands for confidence scoring (ratio of threshold exceeded).
SEVERITY_CRITICAL_RATIO = 1.5
SEVERITY_HIGH_RATIO = 1.2

# Pattern taxonomy stored in ``player_patterns.pattern_type``.
PATTERN_TYPE_PHASE = "phase_weakness"
PATTERN_TYPE_OPENING = "opening_weakness"
