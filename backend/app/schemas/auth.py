from datetime import datetime
from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedUser(BaseModel):
    """
    Sanitized representation of an authenticated Supabase identity.
    Contains claims verified from the Supabase JWT.
    """

    id: str = Field(..., description="Supabase user unique identifier (UUID)")
    email: Optional[str] = Field(default=None, description="User email address")
    role: Optional[str] = Field(default=None, description="Supabase user role (e.g. 'authenticated')")
    app_metadata: Dict[str, Any] = Field(default_factory=dict, description="Supabase app metadata")
    user_metadata: Dict[str, Any] = Field(default_factory=dict, description="Supabase user metadata")

    model_config = ConfigDict(frozen=True)


class UserResponse(BaseModel):
    """
    Safe public response schema for authenticated user profile.
    Explicitly excludes sensitive fields, credentials, passwords, and secrets.
    """

    id: Union[UUID, str] = Field(..., description="Application user unique identifier")
    email: str = Field(..., description="User email address")
    created_at: Optional[datetime] = Field(default=None, description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Account last updated timestamp")

    model_config = ConfigDict(from_attributes=True)
