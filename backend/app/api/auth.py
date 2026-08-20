import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_application_user, get_current_user
from app.db.database import get_db
from app.models.patient import Patient
from app.models.user import User
from app.schemas.auth import AuthenticatedUser, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register or sync application user and patient profile",
    description="Provisions the application User and Patient records in PostgreSQL for the authenticated Supabase identity.",
)
def register_application_user(
    auth_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Idempotent registration/sync endpoint for authenticated Supabase users.
    Creates application User and default Patient profile in PostgreSQL strictly by Supabase Auth UUID.
    """
    try:
        user_uuid = uuid.UUID(auth_user.id)
    except (ValueError, TypeError, AttributeError):
        user_uuid = uuid.uuid4()

    email = auth_user.email or f"{user_uuid}@user.local"
    user = db.query(User).filter(User.id == user_uuid).first()

    if user is None:
        # Check if an old user record exists with the same email (from a deleted Supabase Auth account)
        stale_user = db.query(User).filter(User.email == email, User.id != user_uuid).first()
        if stale_user:
            # Archive old user's email to release the unique constraint without transferring ownership of old medical data
            stale_user.email = f"{stale_user.id}@archived.local"
            db.flush()

        user = User(id=user_uuid, email=email)
        db.add(user)
        patient = Patient(user_id=user.id)
        db.add(patient)
        db.commit()
        db.refresh(user)
        logger.info("Successfully registered application User %s (%s)", user.id, user.email)
    else:
        # Ensure patient profile exists for this exact user UUID
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient:
            patient = Patient(user_id=user.id)
            db.add(patient)
            db.commit()

    return UserResponse.model_validate(user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
    description="Returns the profile information of the currently authenticated application user. Requires a valid Supabase JWT Bearer token in the Authorization header.",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_application_user),
) -> UserResponse:
    """
    Protected endpoint that returns safe profile data for the authenticated application user.
    Returns HTTP 401 if missing, invalid, or expired authentication.
    """
    return UserResponse.model_validate(current_user)
