"""Authentication service using Supabase Auth.

Two responsibilities live here:

1. **Server-driven auth operations** (sign up / sign in / refresh / reset).
   These exist primarily for backend-initiated flows; the frontend talks
   to Supabase directly via `@supabase/ssr` for the user-facing flows.

2. **JWT verification** (:meth:`AuthService.verify_jwt`).
   Tries legacy HS256 (``SUPABASE_JWT_SECRET``), then JWKS (ES256 signing
   keys at ``/auth/v1/.well-known/jwks.json``), then ``auth.get_user``.
   Production **must** set ``SUPABASE_URL``; legacy secret alone does not
   verify magic-link tokens issued after Supabase's signing-keys migration.
"""
from functools import lru_cache
from typing import Any, Dict, Optional

from loguru import logger

import jwt as pyjwt
from jwt import PyJWKClient
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidTokenError,
)

from ...core.config import settings
from ...core.supabase_client import get_supabase

# Supabase asymmetric signing keys (ES256/RS256) — magic-link sessions after 2025 migration
_JWKS_ALGORITHMS = ["ES256", "RS256", "EdDSA", "HS256"]


class AuthError(Exception):
    """Raised when JWT validation or auth resolution fails."""


@lru_cache(maxsize=1)
def _jwks_client() -> Optional[PyJWKClient]:
    if not settings.SUPABASE_URL:
        return None
    jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


class AuthService:
    """Handle authentication operations with Supabase."""

    @staticmethod
    def _decode_claims(token: str, key: Any, algorithms: list[str]) -> Dict[str, Any]:
        return pyjwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.SUPABASE_JWT_AUDIENCE,
            options={"require": ["exp", "sub"]},
        )

    @staticmethod
    def _verify_jwt_hs256(token: str) -> Dict[str, Any]:
        if not settings.SUPABASE_JWT_SECRET:
            raise InvalidTokenError("SUPABASE_JWT_SECRET not configured")
        return AuthService._decode_claims(
            token,
            settings.SUPABASE_JWT_SECRET,
            [settings.SUPABASE_JWT_ALGORITHM],
        )

    @staticmethod
    def _verify_jwt_jwks(token: str) -> Dict[str, Any]:
        client = _jwks_client()
        if client is None:
            raise InvalidTokenError("SUPABASE_URL not configured for JWKS")
        signing_key = client.get_signing_key_from_jwt(token)
        return AuthService._decode_claims(token, signing_key.key, _JWKS_ALGORITHMS)

    @staticmethod
    def _verify_jwt_remote(token: str) -> Dict[str, Any]:
        """Verify via Supabase Auth API (works for all signing key modes)."""
        supabase = get_supabase()
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise AuthError("Token not recognised by Supabase")
        user = response.user
        return {
            "sub": user.id,
            "email": user.email,
            "aud": user.aud or settings.SUPABASE_JWT_AUDIENCE,
            "role": user.role,
        }

    @staticmethod
    def verify_jwt(token: str) -> Dict[str, Any]:
        """Validate a Supabase access token and return its claims.

        Verification order (Supabase JWT signing keys migration):

        1. Legacy HS256 + ``SUPABASE_JWT_SECRET`` (older tokens / anon keys)
        2. JWKS asymmetric keys (ES256 — current magic-link sessions)
        3. ``auth.get_user`` round-trip (last resort)

        Args:
            token: The raw JWT string (no ``Bearer`` prefix).

        Returns:
            Dict containing at minimum ``sub``, ``email``, ``aud``, ``exp``.

        Raises:
            AuthError: If the token is malformed, expired, or invalid.
        """
        if not token:
            raise AuthError("Missing access token")

        errors: list[str] = []

        if settings.SUPABASE_JWT_SECRET:
            try:
                return AuthService._verify_jwt_hs256(token)
            except ExpiredSignatureError:
                raise AuthError("Access token expired") from None
            except InvalidAudienceError:
                raise AuthError("Access token has wrong audience") from None
            except InvalidTokenError as e:
                errors.append(f"legacy HS256: {e}")
                logger.debug("HS256 JWT verification failed, trying JWKS: {}", e)

        try:
            return AuthService._verify_jwt_jwks(token)
        except ExpiredSignatureError:
            raise AuthError("Access token expired") from None
        except InvalidAudienceError:
            raise AuthError("Access token has wrong audience") from None
        except InvalidTokenError as e:
            errors.append(f"JWKS: {e}")
            logger.debug("JWKS JWT verification failed, trying remote: {}", e)

        try:
            return AuthService._verify_jwt_remote(token)
        except AuthError:
            raise
        except Exception as e:  # noqa: BLE001
            errors.append(f"remote: {e}")

        detail = "; ".join(errors) if errors else "unknown verification failure"
        raise AuthError(f"Invalid access token: {detail}")
    
    @staticmethod
    async def send_magic_link(
        email: str,
        *,
        chesscom_username: Optional[str] = None,
        redirect_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a passwordless magic-link email (FR-AUTH-1).

        The frontend normally calls ``signInWithOtp`` directly; this exists
        for backend-initiated flows and smoke scripts.
        """
        try:
            supabase = get_supabase()
            metadata: Dict[str, Any] = {}
            if chesscom_username:
                metadata["chesscom_username"] = chesscom_username.strip().lower()

            options: Dict[str, Any] = {
                "should_create_user": True,
                "data": metadata,
            }
            if redirect_to:
                options["email_redirect_to"] = redirect_to

            supabase.auth.sign_in_with_otp(
                {"email": email.strip(), "options": options}
            )
            logger.info(f"Magic link sent to: {email}")
            return {"success": True, "message": "Magic link sent"}
        except Exception as e:
            logger.error(f"Magic link error for {email}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def sign_up(
        email: str,
        chesscom_username: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register / invite via magic link (no password)."""
        merged = dict(metadata or {})
        if chesscom_username:
            merged["chesscom_username"] = chesscom_username.strip().lower()
        return await AuthService.send_magic_link(
            email, chesscom_username=merged.get("chesscom_username")
        )

    @staticmethod
    async def sign_in(
        email: str,
        chesscom_username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sign in via magic link (no password)."""
        return await AuthService.send_magic_link(email, chesscom_username=chesscom_username)
    
    @staticmethod
    async def sign_out(access_token: str) -> Dict[str, Any]:
        """
        Sign out user and invalidate session.
        
        Args:
            access_token: User's current access token
        
        Returns:
            Dict with success status
        """
        try:
            supabase = get_supabase()
            supabase.auth.sign_out()
            logger.info("User signed out successfully")
            return {"success": True}
        except Exception as e:
            logger.error(f"Sign out error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def get_user(access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user details from access token.
        
        Args:
            access_token: JWT access token
        
        Returns:
            User data or None if invalid
        """
        try:
            supabase = get_supabase()
            # Set the session
            supabase.auth.set_session(access_token, access_token)
            
            user = supabase.auth.get_user()
            if user:
                return user.dict()
            return None
        except Exception as e:
            logger.error(f"Get user error: {str(e)}")
            return None
    
    @staticmethod
    async def refresh_token(refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token from previous session
        
        Returns:
            Dict with new access and refresh tokens
        """
        try:
            supabase = get_supabase()
            
            auth_response = supabase.auth.refresh_session(refresh_token)
            
            if auth_response.session:
                logger.info("Token refreshed successfully")
                return {
                    "access_token": auth_response.session.access_token,
                    "refresh_token": auth_response.session.refresh_token,
                    "success": True
                }
            else:
                return {"success": False, "error": "Token refresh failed"}
                
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def update_user(
        access_token: str,
        email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update user information (email and/or user metadata).
        """
        try:
            supabase = get_supabase()
            supabase.auth.set_session(access_token, access_token)
            
            update_data = {}
            if email:
                update_data["email"] = email
            if metadata:
                update_data["data"] = metadata
            
            user = supabase.auth.update_user(update_data)
            
            if user:
                logger.info("User updated successfully")
                return {"user": user.dict(), "success": True}
            else:
                return {"success": False, "error": "Update failed"}
                
        except Exception as e:
            logger.error(f"User update error: {str(e)}")
            return {"success": False, "error": str(e)}


# Convenience instance
auth_service = AuthService()
