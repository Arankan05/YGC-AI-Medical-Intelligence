from datetime import date
import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.ai_analysis import AIAnalysis
from app.models.allergy import Allergy
from app.models.document import Document
from app.models.finding import Finding
from app.models.lab_result import LabResult
from app.models.medical_event import MedicalEvent
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.extraction import (
    ExtractedAllergy,
    ExtractedFinding,
    ExtractedLabResult,
    ExtractedMedicalEvent,
    ExtractedMedicalRecord,
    ExtractedMedication,
)
from app.services.medical_persistence_service import MedicalPersistenceService

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class MedicalPersistenceServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()
        self.service = MedicalPersistenceService()

        # Seed User & Patient
        self.user = User(
            id=uuid.uuid4(),
            email=f"patient_{uuid.uuid4().hex[:8]}@example.com",
        )
        self.db.add(self.user)
        self.db.commit()

        self.patient = Patient(
            id=uuid.uuid4(),
            user_id=self.user.id,
        )
        self.db.add(self.patient)
        self.db.commit()

        self.document = Document(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            file_name="prescription.pdf",
            file_path="uploads/prescription.pdf",
            document_type="prescription",
            processing_status="COMPLETED",
            extracted_text="Sample extracted text",
        )
        self.db.add(self.document)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        # Clean up records
        self.db.query(AIAnalysis).delete()
        self.db.query(Finding).delete()
        self.db.query(Allergy).delete()
        self.db.query(LabResult).delete()
        self.db.query(Prescription).delete()
        self.db.query(Medication).delete()
        self.db.query(MedicalEvent).delete()
        self.db.query(Document).delete()
        self.db.query(Patient).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_persist_extracted_record_all_entities(self):
        extracted = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Patient treated for bacterial bronchitis.",
            confidence_score=0.94,
            events=[
                ExtractedMedicalEvent(
                    event_type="consultation",
                    event_date=date(2026, 4, 1),
                    title="Pulmonology Visit",
                    description="Chronic cough and wheezing",
                )
            ],
            medications=[
                ExtractedMedication(
                    name="Azithromycin 250mg",
                    normalized_name="azithromycin",
                    dosage="250mg",
                    frequency="once daily",
                    start_date=date(2026, 4, 1),
                    end_date=date(2026, 4, 5),
                    instructions="Take 500mg on day 1, then 250mg daily",
                )
            ],
            lab_results=[
                ExtractedLabResult(
                    test_name="Chest X-Ray",
                    value="Clear lung fields",
                    result_date=date(2026, 4, 1),
                )
            ],
            allergies=[
                ExtractedAllergy(
                    medication_name="Erythromycin",
                    reaction="Severe nausea",
                    severity="moderate",
                )
            ],
            findings=[
                ExtractedFinding(
                    finding_type="diagnosis",
                    title="Acute Bronchitis",
                    description="Infection of the bronchial tree",
                    risk_level="medium",
                    confidence=0.9,
                )
            ],
        )

        counts = self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient.id,
            document_id=self.document.id,
            extracted=extracted,
        )

        assert counts["events"] == 1
        assert counts["medications"] == 1
        assert counts["prescriptions"] == 1
        assert counts["lab_results"] == 1
        assert counts["allergies"] == 1
        assert counts["findings"] == 1
        assert counts["ai_analyses"] == 1

        # Verify DB records
        events = self.db.query(MedicalEvent).filter(MedicalEvent.patient_id == self.patient.id).all()
        assert len(events) == 1
        assert events[0].title == "Pulmonology Visit"
        assert events[0].document_id == self.document.id

        meds = self.db.query(Medication).filter(Medication.patient_id == self.patient.id).all()
        assert len(meds) == 1
        assert meds[0].normalized_name == "azithromycin"

        prescs = self.db.query(Prescription).filter(Prescription.patient_id == self.patient.id).all()
        assert len(prescs) == 1
        assert prescs[0].medication_id == meds[0].id
        assert prescs[0].dosage == "250mg"

        labs = self.db.query(LabResult).filter(LabResult.patient_id == self.patient.id).all()
        assert len(labs) == 1
        assert labs[0].test_name == "Chest X-Ray"

        allergies = self.db.query(Allergy).filter(Allergy.patient_id == self.patient.id).all()
        assert len(allergies) == 1
        assert allergies[0].normalized_medication_name == "erythromycin"

        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient.id).all()
        assert len(findings) == 1
        assert findings[0].title == "Acute Bronchitis"

        analyses = self.db.query(AIAnalysis).filter(AIAnalysis.patient_id == self.patient.id).all()
        assert len(analyses) == 1
        assert analyses[0].analysis_type == "document_extraction"
        assert analyses[0].confidence == 0.94

    def test_medication_deduplication(self):
        # First extraction creates Medication 'amoxicillin'
        rec1 = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Initial Rx",
            confidence_score=0.9,
            medications=[
                ExtractedMedication(name="Amoxicillin 250mg", normalized_name="amoxicillin", dosage="250mg")
            ],
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient.id,
            document_id=self.document.id,
            extracted=rec1,
        )

        meds_before = self.db.query(Medication).filter(Medication.patient_id == self.patient.id).all()
        assert len(meds_before) == 1

        # Second extraction for same patient with different dosage of same medication 'amoxicillin'
        rec2 = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Follow up Rx",
            confidence_score=0.9,
            medications=[
                ExtractedMedication(name="Amoxicillin 500mg", normalized_name="amoxicillin", dosage="500mg")
            ],
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient.id,
            document_id=self.document.id,
            extracted=rec2,
        )

        meds_after = self.db.query(Medication).filter(Medication.patient_id == self.patient.id).all()
        assert len(meds_after) == 1  # Reused medication record, no duplicate!

        prescs_after = self.db.query(Prescription).filter(Prescription.patient_id == self.patient.id).all()
        assert len(prescs_after) == 2  # But 2 distinct prescriptions created!
        assert prescs_after[0].medication_id == meds_after[0].id
        assert prescs_after[1].medication_id == meds_after[0].id
