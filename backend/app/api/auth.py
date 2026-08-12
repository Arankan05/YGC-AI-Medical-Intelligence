from fastapi import APIRouter, Depends

from app.core.security import get_current_application_user
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


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

