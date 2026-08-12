import logging
import uuid
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)

# Reusable HTTPBearer security scheme (auto_error=False enables consistent custom 401 responses)
bearer_scheme = HTTPBearer(auto_error=False)


def get_supabase_client(settings: Settings) -> Client:
    """
    Creates and returns a Supabase client instance for remote auth verification.
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def validate_supabase_token(
    token: str,
    settings: Settings,
) -> AuthenticatedUser:
    """
    Validates a Supabase JWT access token.

    Validation Strategy:
    1. If SUPABASE_JWT_SECRET is configured:
       Performs local cryptographic signature verification using PyJWT with configured
       algorithm (default HS256) and audience (default 'authenticated').
    2. If SUPABASE_JWT_SECRET is not configured:
       Validates the token against the Supabase Auth service (GoTrue API).

    Returns:
        AuthenticatedUser with sanitized identity claims.

    Raises:
        HTTPException(401): If the token is missing, invalid, expired, malformed, or rejected.
    """
    if not token or not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing or empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clean_token = token.strip()

    # Strategy 1: Local cryptographic verification if JWT secret is configured
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                clean_token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=[settings.SUPABASE_JWT_ALGORITHM],
                audience=settings.SUPABASE_JWT_AUDIENCE if settings.SUPABASE_JWT_AUDIENCE else None,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": bool(settings.SUPABASE_JWT_AUDIENCE),
                },
            )

            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload: missing user identifier.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return AuthenticatedUser(
                id=str(user_id),
                email=payload.get("email"),
                role=payload.get("role"),
                app_metadata=payload.get("app_metadata", {}) or {},
                user_metadata=payload.get("user_metadata", {}) or {},
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except (jwt.InvalidTokenError, jwt.DecodeError) as e:
            logger.warning("JWT verification failed: %s", type(e).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Strategy 2: Remote verification via Supabase Auth API
    try:
        supabase_client = get_supabase_client(settings)
        user_response = supabase_client.auth.get_user(clean_token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not authenticate user with Supabase.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        sb_user = user_response.user
        return AuthenticatedUser(
            id=sb_user.id,
            email=sb_user.email,
            role=getattr(sb_user, "role", None),
            app_metadata=getattr(sb_user, "app_metadata", {}) or {},
            user_metadata=getattr(sb_user, "user_metadata", {}) or {},
        )
    except AuthApiError as e:
        logger.warning(
            "Supabase Auth API rejected token: %s",
            e.message if hasattr(e, "message") else str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error during Supabase token verification: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    FastAPI dependency that extracts and validates the Supabase JWT Bearer token
    from the HTTP Authorization header.

    Returns:
        AuthenticatedUser object containing validated Supabase identity.

    Raises:
        HTTPException(401): If Authorization header is missing, malformed, or token is invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not credentials.scheme or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return validate_supabase_token(credentials.credentials, settings)


async def get_current_application_user(
    auth_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that maps the authenticated Supabase identity to the
    corresponding application User record in the PostgreSQL database.

    Ensures strict tenant isolation:
    - Finds only the User record matching the authenticated Supabase identity.
    - Rejects unmapped or unauthorized requests with HTTP 401.
    - Never allows access to another user's record.

    Returns:
        User SQLAlchemy model instance for the authenticated user.

    Raises:
        HTTPException(401): If no application user record exists for this identity.
    """
    user: Optional[User] = None

    # Step 1: Match by primary key UUID (if auth_user.id is a valid UUID)
    try:
        user_uuid = uuid.UUID(auth_user.id)
        user = db.query(User).filter(User.id == user_uuid).first()
    except (ValueError, TypeError, AttributeError):
        pass

    # Step 2: Fallback to matching by unique email if not found by primary key UUID
    if user is None and auth_user.email:
        user = db.query(User).filter(User.email == auth_user.email).first()

    if user is None:
        logger.warning(
            "Authenticated Supabase user has no matching application user record (id=%s, email=%s)",
            auth_user.id,
            auth_user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found in application database. Please ensure your account has been registered.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
