import base64
import logging
import uuid
from functools import lru_cache
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.models.patient import Patient
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


@lru_cache(maxsize=4)
def get_jwks_client(jwks_url: str) -> PyJWKClient:
    """
    Returns a cached PyJWKClient instance for fetching Supabase public signing keys.
    """
    return PyJWKClient(jwks_url, cache_keys=True, max_cached_keys=16)


def validate_supabase_token(
    token: str,
    settings: Settings,
) -> AuthenticatedUser:
    """
    Validates a Supabase JWT access token using a multi-strategy verification pipeline:
    1. Asymmetric JWKS verification (ES256 / RS256) via Supabase .well-known/jwks.json
    2. Local symmetric cryptographic verification (HS256) if SUPABASE_JWT_SECRET is configured
    3. Remote verification via Supabase GoTrue Auth API

    Safe diagnostic logging reports token metadata (length, algorithm, issuer, audience)
    without ever printing the actual token or secret.

    Returns:
        AuthenticatedUser with sanitized identity claims.

    Raises:
        HTTPException(401): If the token is missing, invalid, expired, malformed, or rejected.
    """
    if not token or not isinstance(token, str) or not token.strip():
        logger.warning("Auth validation failed: Authorization token is missing or empty.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing or empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clean_token = token.strip()
    token_len = len(clean_token)

    # Inspect unverified header and payload for safe diagnostics
    try:
        unverified_header = jwt.get_unverified_header(clean_token)
        unverified_payload = jwt.decode(clean_token, options={"verify_signature": False})
        alg = unverified_header.get("alg", "UNKNOWN")
        iss = unverified_payload.get("iss", "UNKNOWN")
        aud = unverified_payload.get("aud", "UNKNOWN")
        logger.info(
            "Validating JWT (len=%d, alg=%s, iss=%s, aud=%s)",
            token_len,
            alg,
            iss,
            aud,
        )
    except Exception as parse_err:
        logger.warning(
            "Failed to parse unverified JWT structure (len=%d): %s",
            token_len,
            type(parse_err).__name__,
        )
        alg, iss, aud = "UNKNOWN", "UNKNOWN", "UNKNOWN"

    last_error: Optional[str] = None

    # Strategy 1: Asymmetric JWKS verification (Standard for Supabase ES256 / RS256)
    if settings.SUPABASE_URL:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        try:
            jwks_client = get_jwks_client(jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(clean_token)
            payload = jwt.decode(
                clean_token,
                signing_key.key,
                algorithms=["ES256", "RS256", "EdDSA", "HS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,  # Checked below explicitly
                },
            )

            # Validate audience
            token_aud = payload.get("aud")
            expected_aud = settings.SUPABASE_JWT_AUDIENCE
            if expected_aud:
                if isinstance(token_aud, list):
                    if expected_aud not in token_aud and "authenticated" not in token_aud:
                        raise jwt.InvalidAudienceError("Audience mismatch in list")
                elif token_aud not in (expected_aud, "authenticated"):
                    raise jwt.InvalidAudienceError(f"Audience mismatch: {token_aud}")

            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload: missing user identifier.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            logger.info("Successfully validated Supabase JWT via JWKS (sub=%s)", user_id)
            return AuthenticatedUser(
                id=str(user_id),
                email=payload.get("email"),
                role=payload.get("role"),
                app_metadata=payload.get("app_metadata", {}) or {},
                user_metadata=payload.get("user_metadata", {}) or {},
            )
        except jwt.ExpiredSignatureError:
            logger.warning("JWKS validation: Token has expired.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as jwks_err:
            last_error = f"JWKS: {type(jwks_err).__name__} ({jwks_err})"
            logger.debug("JWKS validation attempt failed: %s", last_error)

    # Strategy 2: Local symmetric HMAC verification if SUPABASE_JWT_SECRET is configured
    if settings.SUPABASE_JWT_SECRET:
        secrets_to_try = [settings.SUPABASE_JWT_SECRET]
        try:
            # Also try base64 decoded bytes if secret has padding
            decoded_b64 = base64.b64decode(settings.SUPABASE_JWT_SECRET)
            if decoded_b64 and decoded_b64 != settings.SUPABASE_JWT_SECRET.encode():
                secrets_to_try.append(decoded_b64)
        except Exception:
            pass

        for secret in secrets_to_try:
            try:
                payload = jwt.decode(
                    clean_token,
                    secret,
                    algorithms=["HS256", "HS384", "HS512"],
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_aud": False,
                    },
                )

                token_aud = payload.get("aud")
                expected_aud = settings.SUPABASE_JWT_AUDIENCE
                if expected_aud:
                    if isinstance(token_aud, list):
                        if expected_aud not in token_aud and "authenticated" not in token_aud:
                            continue
                    elif token_aud not in (expected_aud, "authenticated"):
                        continue

                user_id = payload.get("sub")
                if not user_id:
                    continue

                logger.info("Successfully validated Supabase JWT via local secret (sub=%s)", user_id)
                return AuthenticatedUser(
                    id=str(user_id),
                    email=payload.get("email"),
                    role=payload.get("role"),
                    app_metadata=payload.get("app_metadata", {}) or {},
                    user_metadata=payload.get("user_metadata", {}) or {},
                )
            except jwt.ExpiredSignatureError:
                logger.warning("Local HMAC validation: Token has expired.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication token has expired.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except Exception as hmac_err:
                last_error = f"HMAC: {type(hmac_err).__name__}"

    # Strategy 3: Remote verification via Supabase Auth API
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            supabase_client = get_supabase_client(settings)
            user_response = supabase_client.auth.get_user(clean_token)

            if user_response and user_response.user:
                sb_user = user_response.user
                logger.info("Successfully validated Supabase JWT via GoTrue Auth API (sub=%s)", sb_user.id)
                return AuthenticatedUser(
                    id=sb_user.id,
                    email=sb_user.email,
                    role=getattr(sb_user, "role", None),
                    app_metadata=getattr(sb_user, "app_metadata", {}) or {},
                    user_metadata=getattr(sb_user, "user_metadata", {}) or {},
                )
        except AuthApiError as api_err:
            last_error = f"GoTrue AuthApiError: {api_err.message if hasattr(api_err, 'message') else api_err}"
            logger.warning("Supabase Auth API rejected token: %s", last_error)
        except Exception as remote_err:
            last_error = f"Remote auth error: {type(remote_err).__name__}"
            logger.debug("Remote Supabase auth attempt failed: %s", last_error)

    logger.warning("All JWT validation strategies failed for token (len=%d). Last error: %s", token_len, last_error)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
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
        logger.info("Authentication rejected: Missing Authorization header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not credentials.scheme or credentials.scheme.lower() != "bearer":
        logger.info("Authentication rejected: Invalid scheme (%s).", credentials.scheme)
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
    - Finds or provisions the User record matching the authenticated Supabase identity.
    - Ensures the default Patient record exists for the user.
    - Never allows access to another user's record.

    Returns:
        User SQLAlchemy model instance for the authenticated user.
    """
    user: Optional[User] = None

    # Step 1: Match by primary key UUID (if auth_user.id is a valid UUID)
    try:
        user_uuid = uuid.UUID(auth_user.id)
        user = db.query(User).filter(User.id == user_uuid).first()
    except (ValueError, TypeError, AttributeError):
        user_uuid = None

    # Step 2: Fallback to matching by unique email if not found by primary key UUID
    if user is None and auth_user.email:
        user = db.query(User).filter(User.email == auth_user.email).first()

    # Step 3: Auto-provision application User and Patient if not yet in PostgreSQL
    if user is None:
        target_id = user_uuid or uuid.uuid4()
        email = auth_user.email or f"{target_id}@user.local"
        user = User(id=target_id, email=email)
        db.add(user)
        patient = Patient(user_id=user.id)
        db.add(patient)
        db.commit()
        db.refresh(user)
        logger.info("Auto-provisioned application User %s (%s) and Patient profile.", user.id, user.email)
    else:
        # Ensure patient profile exists
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient:
            patient = Patient(user_id=user.id)
            db.add(patient)
            db.commit()

    return user
