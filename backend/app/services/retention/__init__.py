"""Retention mechanics — weekly summaries and email delivery stubs."""

from .email_delivery_service import (
    is_email_delivery_configured,
    is_weekly_digest_enabled,
    is_weekly_email_enabled,
    send_weekly_digest_email,
    send_weekly_summary_email,
)
from .weekly_digest_service import (
    WeeklyDigest,
    build_weekly_digest,
    render_weekly_digest_email,
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
    "WeeklyDigest",
    "build_weekly_digest",
    "render_weekly_digest_email",
    "is_email_delivery_configured",
    "is_weekly_email_enabled",
    "is_weekly_digest_enabled",
    "send_weekly_summary_email",
    "send_weekly_digest_email",
]
