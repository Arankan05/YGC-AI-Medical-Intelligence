import uuid
from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

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
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_type = Column(
        String(100),
        nullable=False,
        index=True,
    )
    result = Column(
        JSON,
        nullable=False,
    )
    confidence = Column(
        Float,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="ai_analyses")
    finding = relationship("Finding", back_populates="ai_analyses")
    question = relationship("Question", back_populates="ai_analyses")

    def __repr__(self) -> str:
        return f"<AIAnalysis id={self.id} analysis_type={self.analysis_type} patient_id={self.patient_id}>"
