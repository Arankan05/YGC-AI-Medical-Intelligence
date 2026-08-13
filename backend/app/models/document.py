import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

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
    file_name = Column(
        String(255),
        nullable=False,
    )
    file_path = Column(
        String(1024),
        nullable=False,
    )
    document_type = Column(
        String(50),
        nullable=False,
    )
    processing_status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message = Column(
        Text,
        nullable=True,
    )
    extracted_text = Column(
        Text,
        nullable=True,
    )
    extraction_method = Column(
        String(50),
        nullable=True,
    )
    page_count = Column(
        Integer,
        nullable=True,
    )


    # Relationships
    patient = relationship("Patient", back_populates="documents")
    medical_events = relationship(
        "MedicalEvent",
        back_populates="document",
    )
    prescriptions = relationship(
        "Prescription",
        back_populates="document",
    )
    lab_results = relationship(
        "LabResult",
        back_populates="document",
    )
    allergies = relationship(
        "Allergy",
        back_populates="source_document",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} file_name={self.file_name} status={self.processing_status}>"
