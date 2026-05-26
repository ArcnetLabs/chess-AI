"""Authentication middleware for FastAPI.

Implements ChessIQ's unified auth model:

  - Supabase Auth is the canonical identity layer.
  - Each authenticated request carries a Supabase access token
    (``Authorization: Bearer <jwt>``).
  - :func:`get_current_user` validates the JWT, resolves the local
    :class:`app.models.User` row, auto-provisioning one on first
    contact, and returns the row.

  - Chess.com usernames are linked profile data on that row. Routes do
    not look up users by username for auth.

Why auto-provisioning?
  The Supabase sign-up flow happens entirely client-side; the backend
  only sees the user once they make an authenticated API call. We
  create the local users row lazily on that first call so the
  application doesn't need an explicit "register after Supabase
  signup" step. The row starts with :attr:`User.chesscom_username`
  set to ``None`` and gets populated when the user completes the
  `/onboarding/link-chesscom` step.

  See also :doc:`docs/architecture/auth-system.md` for the full flow.
"""
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import User
from ..services.auth.auth_service import AuthError, AuthService

# auto_error=True so missing Authorization header → 401 automatically.
_required_bearer = HTTPBearer(auto_error=True)
# Optional variant for endpoints that work for both anonymous + signed-in users.
_optional_bearer = HTTPBearer(auto_error=False)


def _resolve_or_provision_user(db: Session, claims: dict) -> User:
    """Look up the local User by ``supabase_user_id``, creating one on first contact.

    The provisioned row carries the email from the JWT but no Chess.com
    link — that's set later through ``POST /users/me/link-chesscom``.
    """
    supabase_user_id = claims.get("sub")
    if not supabase_user_id:
        raise HTTPException(
            status_code=401, detail="Token missing 'sub' claim"
        )

    user = (
        db.query(User)
        .filter(User.supabase_user_id == supabase_user_id)
        .first()
    )
    if user is not None:
        return user

    # First contact for this Supabase user — create the local row.
    email = claims.get("email")
    new_user = User(
        supabase_user_id=supabase_user_id,
        email=email,
        # chesscom_username intentionally left NULL — set via onboarding.
        connection_type="username_only",
        is_chesscom_connected=False,
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as exc:  # noqa: BLE001 — surface as 401, never leak DB errors
        db.rollback()
        logger.error(
            f"Failed to auto-provision user for sub={supabase_user_id}: {exc}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to provision local user"
        ) from exc

    logger.info(
        f"Auto-provisioned local user id={new_user.id} for supabase_user_id={supabase_user_id}"
    )
    return new_user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_required_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: returns the authenticated local :class:`User`.

    Raises:
        HTTPException 401: missing/invalid/expired token.
        HTTPException 500: token valid but local user creation failed.
    """
    try:
        claims = AuthService.verify_jwt(credentials.credentials)
    except AuthError as exc:
        logger.info(f"Auth rejected: {exc}")
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return _resolve_or_provision_user(db, claims)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_optional_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency: returns the authenticated user or ``None``.

    Use for endpoints that are public but expose extra data when signed
    in. Never raises for missing/invalid tokens — silently degrades to
    anonymous.
    """
    if not credentials:
        return None
    try:
        claims = AuthService.verify_jwt(credentials.credentials)
    except AuthError as exc:
        logger.debug(f"Optional auth failed (degrading to anonymous): {exc}")
        return None
    return _resolve_or_provision_user(db, claims)


def require_ownership(current_user: User, target_user_id: int) -> None:
    """Verify the authenticated user owns the resource scoped to ``target_user_id``.

    Use immediately after :func:`get_current_user` on routes whose path
    contains ``{user_id}`` (or any other user-scoped key).

    Raises:
        HTTPException 403: when ``current_user.id != target_user_id``.

    Example::

        @router.post("/{user_id}/fetch")
        async def fetch_games(
            user_id: int,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
            require_ownership(current_user, user_id)
            ...
    """
    if current_user.id != target_user_id:
        # Don't leak whether the target user exists — same response either way.
        raise HTTPException(
            status_code=403,
            detail="You can only access your own resources",
        )
