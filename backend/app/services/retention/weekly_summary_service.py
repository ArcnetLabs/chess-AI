"""Weekly summary aggregation and HTML rendering (P2-RT-02)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.game import Game, GameAnalysis
from app.models.user import User
from app.services.patterns.pattern_service import list_user_patterns
from app.services.profiles.profile_service import get_latest_profile

_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "templates" / "email" / "weekly_summary.html"
)
_SUMMARY_LOOKBACK_DAYS = 7
_TOP_PATTERNS_LIMIT = 5


@dataclass
class WeeklySummary:
    """Aggregated stats for a user's past week."""

    user_id: int
    email: str
    display_name: str
    period_start: datetime
    period_end: datetime
    games_played: int = 0
    games_analyzed: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    avg_accuracy: Optional[float] = None
    avg_acpl: Optional[float] = None
    profile_archetype: Optional[str] = None
    top_patterns: List[dict] = field(default_factory=list)


def _period_bounds() -> Tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=_SUMMARY_LOOKBACK_DAYS)
    return start, end


def _user_display_name(user: User) -> str:
    if user.display_name:
        return user.display_name
    if user.chesscom_username:
        return user.chesscom_username
    return user.email or f"Player #{user.id}"


def _count_result_for_user(game: Game, username: Optional[str]) -> Optional[str]:
    """Return 'win', 'loss', or 'draw' from the user's perspective."""
    if not username:
        return None
    if game.winner == "draw":
        return "draw"
    if game.white_username == username:
        if game.winner == "white":
            return "win"
        if game.winner == "black":
            return "loss"
    elif game.black_username == username:
        if game.winner == "black":
            return "win"
        if game.winner == "white":
            return "loss"
    return None


def build_weekly_summary(db: Session, user_id: int) -> Optional[WeeklySummary]:
    """
    Build a weekly summary for ``user_id``.

    Returns ``None`` when the user does not exist or has no email on file.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.email:
        return None

    period_start, period_end = _period_bounds()
    username = user.chesscom_username

    games: List[Game] = (
        db.query(Game)
        .filter(
            Game.user_id == user_id,
            Game.end_time >= period_start,
            Game.end_time <= period_end,
        )
        .all()
    )

    wins = losses = draws = 0
    for game in games:
        outcome = _count_result_for_user(game, username)
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        elif outcome == "draw":
            draws += 1

    game_ids = [g.id for g in games]
    analyses: List[GameAnalysis] = []
    if game_ids:
        analyses = (
            db.query(GameAnalysis)
            .filter(GameAnalysis.game_id.in_(game_ids))
            .all()
        )

    accuracies = [
        a.accuracy_percentage
        for a in analyses
        if a.accuracy_percentage is not None
    ]
    acpls = [a.user_acpl for a in analyses if a.user_acpl is not None]

    profile = get_latest_profile(db, user_id)
    patterns = list_user_patterns(db, user_id, limit=_TOP_PATTERNS_LIMIT)
    top_patterns = [
        {
            "pattern_type": p.pattern_type,
            "severity": p.severity,
            "description": (p.pattern_description or "")[:120],
        }
        for p in patterns
    ]

    return WeeklySummary(
        user_id=user_id,
        email=user.email,
        display_name=_user_display_name(user),
        period_start=period_start,
        period_end=period_end,
        games_played=len(games),
        games_analyzed=len(analyses),
        wins=wins,
        losses=losses,
        draws=draws,
        avg_accuracy=round(sum(accuracies) / len(accuracies), 1) if accuracies else None,
        avg_acpl=round(sum(acpls) / len(acpls), 1) if acpls else None,
        profile_archetype=profile.archetype if profile else None,
        top_patterns=top_patterns,
    )


def _format_period(summary: WeeklySummary) -> str:
    start = summary.period_start.strftime("%b %d")
    end = summary.period_end.strftime("%b %d, %Y")
    return f"{start} – {end}"


def _format_patterns_html(patterns: List[dict]) -> str:
    if not patterns:
        return "<li>No patterns detected yet — keep playing and analyzing!</li>"
    items = []
    for p in patterns:
        label = p.get("pattern_type", "pattern").replace("_", " ").title()
        severity = p.get("severity", "")
        desc = p.get("description", "")
        items.append(
            f"<li><strong>{label}</strong>"
            f"{f' ({severity})' if severity else ''}"
            f"{f' — {desc}' if desc else ''}</li>"
        )
    return "\n".join(items)


def render_weekly_summary_email(summary: WeeklySummary) -> Tuple[str, str]:
    """Render subject and HTML body from a weekly summary."""
    period_label = _format_period(summary)
    subject = f"Your ChessIQ week in review — {period_label}"

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    accuracy_line = (
        f"{summary.avg_accuracy}%"
        if summary.avg_accuracy is not None
        else "—"
    )
    acpl_line = (
        f"{summary.avg_acpl}"
        if summary.avg_acpl is not None
        else "—"
    )
    archetype_line = summary.profile_archetype or "Building your profile"

    replacements = {
        "{{display_name}}": summary.display_name,
        "{{period_label}}": period_label,
        "{{games_played}}": str(summary.games_played),
        "{{games_analyzed}}": str(summary.games_analyzed),
        "{{wins}}": str(summary.wins),
        "{{losses}}": str(summary.losses),
        "{{draws}}": str(summary.draws),
        "{{avg_accuracy}}": accuracy_line,
        "{{avg_acpl}}": acpl_line,
        "{{profile_archetype}}": archetype_line,
        "{{top_patterns_html}}": _format_patterns_html(summary.top_patterns),
        "{{drills_completed_week}}": "—",
        "{{training_completion_rate}}": "—",
        "{{active_training_plan_title}}": "—",
        "{{coaching_tip}}": "",
    }

    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return subject, html
