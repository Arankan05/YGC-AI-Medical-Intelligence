import uuid
from sqlalchemy import Column, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class DoctorSearch(Base):
    __tablename__ = "doctor_searches"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    specialty = Column(
        String(100),
        nullable=False,
        index=True,
    )
    location_query = Column(
        String(255),
        nullable=False,
    )
    latitude = Column(
        Float,
        nullable=True,
    )
    longitude = Column(
        Float,
        nullable=True,
    )
    availability_preference = Column(
        String(100),
        nullable=True,
    )
    search_radius = Column(
        Float,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="doctor_searches")
    finding = relationship("Finding", back_populates="doctor_searches")
    recommendations = relationship(
        "DoctorRecommendation",
        back_populates="doctor_search",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DoctorSearch id={self.id} specialty={self.specialty} location_query={self.location_query}>"
