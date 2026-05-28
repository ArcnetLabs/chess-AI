"""Adaptive training plan services (P3-TR-*)."""

from .drill_generator_service import (
    build_drill_attempt_row,
    build_drill_prompt,
    generate_training_plan,
    get_next_plan_version,
    pick_best_occurrence,
    resolve_drill_type,
    select_patterns_for_drills,
)
from .training_progress_service import (
    TrainingProgressStats,
    complete_drill_attempt,
    compute_training_progress,
    training_progress_to_dict,
)

__all__ = [
    "TrainingProgressStats",
    "build_drill_attempt_row",
    "build_drill_prompt",
    "complete_drill_attempt",
    "compute_training_progress",
    "generate_training_plan",
    "get_next_plan_version",
    "pick_best_occurrence",
    "resolve_drill_type",
    "select_patterns_for_drills",
    "training_progress_to_dict",
]
