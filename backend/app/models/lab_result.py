import uuid
from sqlalchemy import Column, Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class LabResult(Base):
    __tablename__ = "lab_results"

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
    test_name = Column(
        String(255),
        nullable=False,
        index=True,
    )
    value = Column(
        String(100),
        nullable=False,
    )
    unit = Column(
        String(50),
        nullable=True,
    )
    reference_range = Column(
        String(100),
        nullable=True,
    )
    result_date = Column(
        Date,
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="lab_results")
    document = relationship("Document", back_populates="lab_results")

    def __repr__(self) -> str:
        return f"<LabResult id={self.id} test_name={self.test_name} value={self.value}>"
