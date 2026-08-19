import uuid
from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Finding(Base):
    __tablename__ = "findings"

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
    finding_type = Column(
        String(100),
        nullable=False,
        index=True,
    )
    title = Column(
        String(255),
        nullable=False,
    )
    description = Column(
        Text,
        nullable=False,
    )
    risk_level = Column(
        String(50),
        nullable=True,
        index=True,
    )
    confidence = Column(
        Float,
        nullable=True,
    )
    recommendation = Column(
        Text,
        nullable=True,
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
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="findings")
    source_document = relationship(
        "Document",
        back_populates="findings",
    )
    ai_analyses = relationship(
        "AIAnalysis",
        back_populates="finding",
    )
    doctor_searches = relationship(
        "DoctorSearch",
        back_populates="finding",
    )

    def __repr__(self) -> str:
        return f"<Finding id={self.id} title={self.title} risk_level={self.risk_level}>"
