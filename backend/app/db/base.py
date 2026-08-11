"""
Import Base and all SQLAlchemy models so that Alembic and metadata tools
can automatically discover all model definitions on Base.metadata.
"""

from app.db.database import Base
from app.models.user import User
from app.models.patient import Patient
from app.models.document import Document
from app.models.medical_event import MedicalEvent
from app.models.medication import Medication
from app.models.prescription import Prescription
from app.models.lab_result import LabResult
from app.models.allergy import Allergy
from app.models.finding import Finding
from app.models.question import Question
from app.models.ai_analysis import AIAnalysis
from app.models.doctor_search import DoctorSearch
from app.models.doctor_recommendation import DoctorRecommendation

__all__ = [
    "Base",
    "User",
    "Patient",
    "Document",
    "MedicalEvent",
    "Medication",
    "Prescription",
    "LabResult",
    "Allergy",
    "Finding",
    "Question",
    "AIAnalysis",
    "DoctorSearch",
    "DoctorRecommendation",
]
