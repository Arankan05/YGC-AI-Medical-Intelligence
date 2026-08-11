import uuid
from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    user = relationship("User", back_populates="patients")
    documents = relationship(
        "Document",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    medical_events = relationship(
        "MedicalEvent",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    medications = relationship(
        "Medication",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    prescriptions = relationship(
        "Prescription",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    lab_results = relationship(
        "LabResult",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    allergies = relationship(
        "Allergy",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    findings = relationship(
        "Finding",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    questions = relationship(
        "Question",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    ai_analyses = relationship(
        "AIAnalysis",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    doctor_searches = relationship(
        "DoctorSearch",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} user_id={self.user_id}>"
