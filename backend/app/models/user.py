import uuid
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class User(Base):
    """
    Application user model linked directly to the authenticated Supabase Auth identity (auth.users).

    Architecture:
    Supabase Auth (auth.users UUID) -> application User.id (UUID) -> Patient.user_id -> Medical Data

    Security & Privacy:
    - User.id matches the Supabase Auth user UUID (JWT 'sub' claim).
    - Contains only safe profile data (id, email, created_at, updated_at).
    - Never stores passwords, access tokens, refresh tokens, or secrets.
    """

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    patients = relationship(
        "Patient",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
