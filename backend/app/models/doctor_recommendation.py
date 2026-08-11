import uuid
from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class DoctorRecommendation(Base):
    __tablename__ = "doctor_recommendations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    doctor_search_id = Column(
        UUID(as_uuid=True),
        ForeignKey("doctor_searches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_name = Column(
        String(255),
        nullable=False,
    )
    specialty = Column(
        String(100),
        nullable=False,
        index=True,
    )
    address = Column(
        Text,
        nullable=True,
    )
    latitude = Column(
        Float,
        nullable=True,
    )
    longitude = Column(
        Float,
        nullable=True,
    )
    distance_km = Column(
        Float,
        nullable=True,
    )
    phone = Column(
        String(50),
        nullable=True,
    )
    website = Column(
        String(500),
        nullable=True,
    )
    opening_hours = Column(
        Text,
        nullable=True,
    )
    source = Column(
        String(100),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    doctor_search = relationship("DoctorSearch", back_populates="recommendations")

    def __repr__(self) -> str:
        return f"<DoctorRecommendation id={self.id} provider_name={self.provider_name} specialty={self.specialty}>"
