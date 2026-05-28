"""Retention mechanics — weekly summaries and email delivery stubs."""

from .email_delivery_service import (
    is_email_delivery_configured,
    is_weekly_email_enabled,
    send_weekly_summary_email,
)
from .weekly_summary_service import (
    WeeklySummary,
    build_weekly_summary,
    render_weekly_summary_email,
)

__all__ = [
    "WeeklySummary",
    "build_weekly_summary",
    "render_weekly_summary_email",
    "is_email_delivery_configured",
    "is_weekly_email_enabled",
    "send_weekly_summary_email",
]
