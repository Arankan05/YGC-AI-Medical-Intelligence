import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Medication(Base):
    __tablename__ = "medications"

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
    name = Column(
        String(255),
        nullable=False,
    )
    normalized_name = Column(
        String(255),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="medications")
    prescriptions = relationship(
        "Prescription",
        back_populates="medication",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Medication id={self.id} name={self.name} normalized_name={self.normalized_name}>"
