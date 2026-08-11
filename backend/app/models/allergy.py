import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Allergy(Base):
    __tablename__ = "allergies"

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
    medication_name = Column(
        String(255),
        nullable=False,
    )
    normalized_medication_name = Column(
        String(255),
        nullable=False,
        index=True,
    )
    reaction = Column(
        Text,
        nullable=True,
    )
    severity = Column(
        String(50),
        nullable=True,
        index=True,
    )
    source_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="allergies")
    source_document = relationship("Document", back_populates="allergies")

    def __repr__(self) -> str:
        return f"<Allergy id={self.id} medication_name={self.medication_name} severity={self.severity}>"
