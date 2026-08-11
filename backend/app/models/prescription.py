import uuid
from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

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
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    medication_id = Column(
        UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dosage = Column(
        String(100),
        nullable=True,
    )
    frequency = Column(
        String(100),
        nullable=True,
    )
    start_date = Column(
        Date,
        nullable=True,
    )
    end_date = Column(
        Date,
        nullable=True,
    )
    instructions = Column(
        Text,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="prescriptions")
    document = relationship("Document", back_populates="prescriptions")
    medication = relationship("Medication", back_populates="prescriptions")

    def __repr__(self) -> str:
        return f"<Prescription id={self.id} patient_id={self.patient_id} medication_id={self.medication_id}>"
