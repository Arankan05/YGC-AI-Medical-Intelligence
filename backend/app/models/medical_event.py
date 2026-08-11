import uuid
from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class MedicalEvent(Base):
    __tablename__ = "medical_events"

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
    event_type = Column(
        String(100),
        nullable=False,
        index=True,
    )
    event_date = Column(
        Date,
        nullable=True,
        index=True,
    )
    title = Column(
        String(255),
        nullable=False,
    )
    description = Column(
        Text,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="medical_events")
    document = relationship("Document", back_populates="medical_events")

    def __repr__(self) -> str:
        return f"<MedicalEvent id={self.id} title={self.title} event_type={self.event_type}>"
