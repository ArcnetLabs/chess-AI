"""Authentication service using Supabase Auth.

Two responsibilities live here:

1. **Server-driven auth operations** (sign up / sign in / refresh / reset).
   These exist primarily for backend-initiated flows; the frontend talks
   to Supabase directly via `@supabase/ssr` for the user-facing flows.

2. **JWT verification** (:meth:`AuthService.verify_jwt`).
   Every authenticated request to the FastAPI backend validates the
   Supabase access token *locally* using PyJWT and the project's JWT
   secret. This avoids a network round-trip per request and keeps
   `Depends(get_current_user)` cheap.

   If ``SUPABASE_JWT_SECRET`` is unset (development), the verifier falls
   back to calling Supabase's userinfo endpoint via the SDK. This is
   slower but lets developers run the backend without configuring the
   secret explicitly. Production deployments **must** set the secret.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

import jwt as pyjwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidTokenError,
)

from ...core.supabase_client import get_supabase, get_supabase_admin
from ...core.config import settings


class AuthError(Exception):
    """Raised when JWT validation or auth resolution fails."""


class AuthService:
    """Handle authentication operations with Supabase."""

    @staticmethod
    def verify_jwt(token: str) -> Dict[str, Any]:
        """Validate a Supabase access token and return its claims.

        Primary path: local HS256 verification using
        ``settings.SUPABASE_JWT_SECRET``. This is the production path and
        is hot-path-safe (no I/O).

        Fallback path: ``supabase.auth.get_user(token)`` — used only when
        the JWT secret is not configured. Performs an HTTP call to
        Supabase's ``/auth/v1/user`` endpoint.

        Args:
            token: The raw JWT string (no ``Bearer`` prefix).

        Returns:
            Dict containing at minimum ``sub`` (Supabase user UUID),
            ``email``, ``aud``, ``exp``.

        Raises:
            AuthError: If the token is malformed, expired, or has an
                invalid signature/audience.
        """
        if not token:
            raise AuthError("Missing access token")

        # Primary path: local signature verification.
        if settings.SUPABASE_JWT_SECRET:
            try:
                claims = pyjwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=[settings.SUPABASE_JWT_ALGORITHM],
                    audience=settings.SUPABASE_JWT_AUDIENCE,
                    options={"require": ["exp", "sub"]},
                )
                return claims
            except ExpiredSignatureError:
                raise AuthError("Access token expired")
            except InvalidAudienceError:
                raise AuthError("Access token has wrong audience")
            except InvalidTokenError as e:
                raise AuthError(f"Invalid access token: {e}") from e

        # Fallback path: SDK round-trip (dev-only).
        logger.warning(
            "SUPABASE_JWT_SECRET not set — falling back to SDK auth.get_user(). "
            "Configure the secret for production."
        )
        try:
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
        except AuthError:
            raise
        except Exception as e:  # noqa: BLE001 — SDK raises various types
            raise AuthError(f"Token verification failed: {e}") from e
    
    @staticmethod
    async def sign_up(email: str, password: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Register a new user with email and password.
        
        Args:
            email: User email address
            password: User password (min 6 characters)
            metadata: Additional user metadata (e.g., chesscom_username)
        
        Returns:
            Dict containing user data and session
        """
        try:
            supabase = get_supabase()
            
            # Sign up user with Supabase Auth
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata or {}
                }
            })
            
            if auth_response.user:
                logger.info(f"User signed up successfully: {email}")
                return {
                    "user": auth_response.user,
                    "session": auth_response.session,
                    "success": True
                }
            else:
                logger.warning(f"Sign up failed for: {email}")
                return {"success": False, "error": "Sign up failed"}
                
        except Exception as e:
            logger.error(f"Sign up error for {email}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def sign_in(email: str, password: str) -> Dict[str, Any]:
        """
        Sign in user with email and password.
        
        Args:
            email: User email address
            password: User password
        
        Returns:
            Dict containing user data and session token
        """
        try:
            supabase = get_supabase()
            
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.session:
                logger.info(f"User signed in successfully: {email}")
                return {
                    "user": auth_response.user,
                    "session": auth_response.session,
                    "access_token": auth_response.session.access_token,
                    "refresh_token": auth_response.session.refresh_token,
                    "success": True
                }
            else:
                logger.warning(f"Sign in failed for: {email}")
                return {"success": False, "error": "Invalid credentials"}
                
        except Exception as e:
            logger.error(f"Sign in error for {email}: {str(e)}")
            return {"success": False, "error": str(e)}
    
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
    async def reset_password_email(email: str) -> Dict[str, Any]:
        """
        Send password reset email.
        
        Args:
            email: User email address
        
        Returns:
            Dict with success status
        """
        try:
            supabase = get_supabase()
            supabase.auth.reset_password_email(email)
            logger.info(f"Password reset email sent to: {email}")
            return {"success": True, "message": "Password reset email sent"}
        except Exception as e:
            logger.error(f"Password reset error for {email}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def update_user(
        access_token: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update user information.
        
        Args:
            access_token: User's access token
            email: New email (optional)
            password: New password (optional)
            metadata: Updated metadata (optional)
        
        Returns:
            Dict with updated user data
        """
        try:
            supabase = get_supabase()
            supabase.auth.set_session(access_token, access_token)
            
            update_data = {}
            if email:
                update_data["email"] = email
            if password:
                update_data["password"] = password
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
