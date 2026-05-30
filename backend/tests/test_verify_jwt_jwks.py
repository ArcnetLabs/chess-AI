"""JWT verification supports legacy HS256 and JWKS (ES256) signing keys."""
import pytest
from unittest.mock import patch

from jwt.exceptions import InvalidTokenError

from app.core.config import settings
from app.services.auth.auth_service import AuthService


@pytest.mark.auth
def test_verify_jwt_falls_back_to_jwks_when_hs256_fails(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "wrong-secret")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")

    expected = {
        "sub": "user-uuid",
        "email": "a@b.com",
        "aud": "authenticated",
        "exp": 9999999999,
    }

    with patch.object(
        AuthService,
        "_verify_jwt_hs256",
        side_effect=InvalidTokenError("bad sig"),
    ), patch.object(
        AuthService,
        "_verify_jwt_jwks",
        return_value=expected,
    ) as jwks_mock:
        claims = AuthService.verify_jwt("fake.jwt.token")

    assert claims["sub"] == "user-uuid"
    jwks_mock.assert_called_once()


@pytest.mark.auth
def test_verify_jwt_remote_last_resort(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")
    monkeypatch.setattr(settings, "SUPABASE_URL", "")

    expected = {"sub": "remote-user", "email": "x@y.com", "aud": "authenticated"}

    with patch.object(
        AuthService,
        "_verify_jwt_jwks",
        side_effect=InvalidTokenError("no jwks"),
    ), patch.object(
        AuthService,
        "_verify_jwt_remote",
        return_value=expected,
    ):
        claims = AuthService.verify_jwt("any-token")

    assert claims["sub"] == "remote-user"
