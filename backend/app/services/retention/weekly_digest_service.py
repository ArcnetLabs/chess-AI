"""Proactive coaching weekly digest — extends weekly summary (P3-PC-01)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.training import DrillAttempt, TrainingPlan
from app.services.retention.weekly_summary_service import (
    WeeklySummary,
    _format_period,
    _format_patterns_html,
    build_weekly_summary,
)
from app.services.training.training_progress_service import compute_training_progress

_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "templates" / "email" / "weekly_summary.html"
)


@dataclass
class WeeklyDigest(WeeklySummary):
    """Weekly summary enriched with training progress and coaching tips."""

    drills_completed_week: int = 0
    training_completion_rate: Optional[float] = None
    active_training_plan_title: Optional[str] = None
    coaching_tip: str = ""


def _build_coaching_tip(top_patterns: List[dict]) -> str:
    """Template coaching tip from the user's top weakness pattern (no LLM)."""
    if not top_patterns:
        return (
            "Keep playing and analyzing — your personalized coaching tips "
            "will appear as we detect more patterns in your games."
        )

    top = top_patterns[0]
    label = top.get("pattern_type", "pattern").replace("_", " ").title()
    severity = top.get("severity", "")
    desc = (top.get("description") or "").strip()

    severity_hint = f" ({severity})" if severity else ""
    if desc:
        return (
            f"Focus area this week: {label}{severity_hint}. {desc} "
            f"Try targeted drills in ChessIQ to address this pattern."
        )
    return (
        f"Focus area this week: {label}{severity_hint}. "
        f"Work through training drills that target this weakness."
    )


def _count_drills_completed_in_period(
    db: Session,
    user_id: int,
    period_start,
    period_end,
) -> int:
    return (
        db.query(func.count(DrillAttempt.id))
        .filter(
            DrillAttempt.user_id == user_id,
            DrillAttempt.status == "completed",
            DrillAttempt.completed_at >= period_start,
            DrillAttempt.completed_at <= period_end,
        )
        .scalar()
    ) or 0


def _active_plan_title(db: Session, plan_id: Optional[int]) -> Optional[str]:
    if plan_id is None:
        return None
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
    return plan.title if plan else None


def build_weekly_digest(db: Session, user_id: int) -> Optional[WeeklyDigest]:
    """
    Build a proactive coaching weekly digest for ``user_id``.

    Returns ``None`` when the user does not exist or has no email on file.
    """
    summary = build_weekly_summary(db, user_id)
    if summary is None:
        return None

    progress = compute_training_progress(db, user_id)
    drills_completed_week = _count_drills_completed_in_period(
        db,
        user_id,
        summary.period_start,
        summary.period_end,
    )

    training_rate = progress.active_plan_completion_rate
    if training_rate is None and progress.total_drills:
        training_rate = progress.completion_rate

    return WeeklyDigest(
        user_id=summary.user_id,
        email=summary.email,
        display_name=summary.display_name,
        period_start=summary.period_start,
        period_end=summary.period_end,
        games_played=summary.games_played,
        games_analyzed=summary.games_analyzed,
        wins=summary.wins,
        losses=summary.losses,
        draws=summary.draws,
        avg_accuracy=summary.avg_accuracy,
        avg_acpl=summary.avg_acpl,
        profile_archetype=summary.profile_archetype,
        top_patterns=summary.top_patterns,
        drills_completed_week=drills_completed_week,
        training_completion_rate=training_rate,
        active_training_plan_title=_active_plan_title(db, progress.active_plan_id),
        coaching_tip=_build_coaching_tip(summary.top_patterns),
    )


def _format_completion_rate(rate: Optional[float]) -> str:
    if rate is None:
        return "—"
    return f"{round(rate * 100)}%"


def render_weekly_digest_email(digest: WeeklyDigest) -> Tuple[str, str]:
    """Render subject and HTML body from a weekly digest."""
    period_label = _format_period(digest)
    subject = f"Your ChessIQ coaching digest — {period_label}"

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    accuracy_line = (
        f"{digest.avg_accuracy}%"
        if digest.avg_accuracy is not None
        else "—"
    )
    acpl_line = (
        f"{digest.avg_acpl}"
        if digest.avg_acpl is not None
        else "—"
    )
    archetype_line = digest.profile_archetype or "Building your profile"
    plan_line = digest.active_training_plan_title or "No active plan"

    replacements = {
        "{{display_name}}": digest.display_name,
        "{{period_label}}": period_label,
        "{{games_played}}": str(digest.games_played),
        "{{games_analyzed}}": str(digest.games_analyzed),
        "{{wins}}": str(digest.wins),
        "{{losses}}": str(digest.losses),
        "{{draws}}": str(digest.draws),
        "{{avg_accuracy}}": accuracy_line,
        "{{avg_acpl}}": acpl_line,
        "{{profile_archetype}}": archetype_line,
        "{{top_patterns_html}}": _format_patterns_html(digest.top_patterns),
        "{{drills_completed_week}}": str(digest.drills_completed_week),
        "{{training_completion_rate}}": _format_completion_rate(
            digest.training_completion_rate
        ),
        "{{active_training_plan_title}}": plan_line,
        "{{coaching_tip}}": digest.coaching_tip,
    }

    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return subject, html
