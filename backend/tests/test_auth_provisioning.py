"""Local user provisioning / identity rebinding (auth middleware).

Covers the production failure where a re-created Supabase identity hit a 500:
the browser's stale token for a *deleted* identity provisioned a row keyed to
that dead id, and the live identity's first request then collided with the
existing row on the unique email.
"""

import pytest

from app.middleware.auth_middleware import _resolve_or_provision_user
from app.models.user import User


def _claims(sub: str, email: str, chesscom: str | None = None) -> dict:
    claims = {"sub": sub, "email": email}
    if chesscom is not None:
        claims["user_metadata"] = {"chesscom_username": chesscom}
    return claims


class TestResolveOrProvisionUser:
    def test_provisions_row_for_unseen_identity(self, db):
        user = _resolve_or_provision_user(db, _claims("sub-new", "new@example.com", "newplayer"))

        assert user.id is not None
        assert user.supabase_user_id == "sub-new"
        assert user.email == "new@example.com"
        assert user.chesscom_username == "newplayer"
        assert user.is_chesscom_connected is True

    def test_returns_existing_row_for_known_identity(self, db):
        existing = User(
            email="known@example.com",
            supabase_user_id="sub-known",
            connection_type="username_only",
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

        user = _resolve_or_provision_user(db, _claims("sub-known", "known@example.com"))

        assert user.id == existing.id
        assert db.query(User).filter(User.email == "known@example.com").count() == 1

    def test_rebinds_email_row_to_recreated_identity(self, db):
        """A re-created Supabase identity must reuse the human's existing row."""
        stale = User(
            email="rereg@example.com",
            supabase_user_id="dead-identity-id",
            connection_type="username_only",
        )
        db.add(stale)
        db.commit()
        db.refresh(stale)
        stale_id = stale.id

        user = _resolve_or_provision_user(
            db, _claims("live-identity-id", "rereg@example.com", "rereg_player")
        )

        assert user.id == stale_id
        assert user.supabase_user_id == "live-identity-id"
        assert db.query(User).filter(User.email == "rereg@example.com").count() == 1

    def test_rebind_preserves_existing_chesscom_link(self, db):
        stale = User(
            email="linked@example.com",
            supabase_user_id="dead-identity-id",
            chesscom_username="alleyer16",
            connection_type="username_only",
            is_chesscom_connected=True,
        )
        db.add(stale)
        db.commit()
        db.refresh(stale)

        user = _resolve_or_provision_user(
            db, _claims("live-identity-id", "linked@example.com", "someone_else")
        )

        assert user.chesscom_username == "alleyer16"

    def test_missing_sub_is_rejected(self, db):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            _resolve_or_provision_user(db, {"email": "no-sub@example.com"})

        assert excinfo.value.status_code == 401
