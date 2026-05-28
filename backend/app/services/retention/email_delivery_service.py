"""Email delivery stub — no real sends until configured (P2-RT-02)."""
from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from app.core.config import settings
from app.models.user import User
from app.services.retention.weekly_digest_service import (
    WeeklyDigest,
    render_weekly_digest_email,
)
from app.services.retention.weekly_summary_service import (
    WeeklySummary,
    render_weekly_summary_email,
)

WEEKLY_SUMMARY_PREF_KEY = "weekly_summary_enabled"
DEFAULT_WEEKLY_SUMMARY_ENABLED = True
WEEKLY_DIGEST_PREF_KEY = "weekly_digest_enabled"
DEFAULT_WEEKLY_DIGEST_ENABLED = True


def is_weekly_email_enabled(user: User) -> bool:
    """Return whether this user opted in to weekly summary emails."""
    prefs = user.notification_preferences or {}
    return bool(prefs.get(WEEKLY_SUMMARY_PREF_KEY, DEFAULT_WEEKLY_SUMMARY_ENABLED))


def is_weekly_digest_enabled(user: User) -> bool:
    """Return whether this user opted in to weekly coaching digest emails."""
    prefs = user.notification_preferences or {}
    return bool(prefs.get(WEEKLY_DIGEST_PREF_KEY, DEFAULT_WEEKLY_DIGEST_ENABLED))


def is_email_delivery_configured() -> bool:
    """True when outbound email is enabled and minimally configured."""
    if not settings.EMAIL_DELIVERY_ENABLED:
        return False
    return bool(settings.EMAIL_FROM_ADDRESS.strip())


def send_weekly_summary_email(
    user: User,
    summary: WeeklySummary,
) -> Dict[str, Any]:
    """
    Send (or stub) the weekly summary email for ``user``.

    Returns ``{"status": "skipped", ...}`` when delivery is not configured.
    """
    if not is_weekly_email_enabled(user):
        return {
            "status": "skipped",
            "reason": "weekly_summary_disabled",
            "user_id": user.id,
        }

    subject, html = render_weekly_summary_email(summary)

    if not is_email_delivery_configured():
        logger.info(
            f"Weekly summary email stub for user_id={user.id} "
            f"(delivery disabled): subject={subject!r}"
        )
        return {
            "status": "skipped",
            "reason": "email_delivery_not_configured",
            "user_id": user.id,
            "subject": subject,
            "html_length": len(html),
        }

    # Real provider integration deferred until EMAIL_DELIVERY_ENABLED is wired.
    logger.warning(
        f"EMAIL_DELIVERY_ENABLED=true but no provider implemented; "
        f"skipping send for user_id={user.id}"
    )
    return {
        "status": "skipped",
        "reason": "provider_not_implemented",
        "user_id": user.id,
        "subject": subject,
    }


def send_weekly_digest_email(
    user: User,
    digest: WeeklyDigest,
) -> Dict[str, Any]:
    """
    Send (or stub) the weekly coaching digest email for ``user``.

    Returns ``{"status": "skipped", ...}`` when delivery is not configured.
    """
    if not is_weekly_digest_enabled(user):
        return {
            "status": "skipped",
            "reason": "weekly_digest_disabled",
            "user_id": user.id,
        }

    subject, html = render_weekly_digest_email(digest)

    if not is_email_delivery_configured():
        logger.info(
            f"Weekly digest email stub for user_id={user.id} "
            f"(delivery disabled): subject={subject!r}"
        )
        return {
            "status": "skipped",
            "reason": "email_delivery_not_configured",
            "user_id": user.id,
            "subject": subject,
            "html_length": len(html),
        }

    logger.warning(
        f"EMAIL_DELIVERY_ENABLED=true but no provider implemented; "
        f"skipping digest send for user_id={user.id}"
    )
    return {
        "status": "skipped",
        "reason": "provider_not_implemented",
        "user_id": user.id,
        "subject": subject,
    }
