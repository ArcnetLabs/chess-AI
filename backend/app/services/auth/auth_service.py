"""Authentication service using Supabase Auth."""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from ...core.supabase_client import get_supabase, get_supabase_admin
from ...core.config import settings


class AuthService:
    """Handle authentication operations with Supabase."""
    
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
