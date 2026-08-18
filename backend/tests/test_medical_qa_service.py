import unittest
import uuid
from datetime import date
from unittest.mock import MagicMock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
from app.models.question import Question
from app.models.user import User
from app.services.ai.base_provider import (
    AIAuthenticationError,
    AIRateLimitError,
    AIServiceError,
    BaseAIProvider,
)
from app.services.medical_qa_service import MedicalQaService


class MockTestAIProvider(BaseAIProvider):
    def __init__(self, response_payload=None, exception_to_raise=None):
        self.response_payload = response_payload or {
            "paragraphs": ["Your prescribed Metformin dosage is 500mg twice daily."],
            "citations": [
                {
                    "document_id": str(uuid.uuid4()),
                    "document_title": "Prescription_Aug2026.pdf",
                    "page": 1,
                    "quote": "Metformin HCl 500mg PO BID",
                }
            ],
            "confidence": 95,
            "guidance": "Answered strictly from your uploaded medical records.",
            "refusal": None,
            "cta": None,
        }
        self.exception_to_raise = exception_to_raise
        self.last_prompt = None
        self.last_system_instruction = None

    def generate_text(self, prompt: str, system_instruction=None, temperature=0.1) -> str:
        if self.exception_to_raise:
            raise self.exception_to_raise
        return "mock text"

    def generate_structured(self, prompt: str, system_instruction=None, temperature=0.1):
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        if self.exception_to_raise:
            raise self.exception_to_raise
        return self.response_payload


class MedicalQaServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Create primary test user & patient
        self.user = User(
            id=uuid.uuid4(),
            email="patient.a@example.com",
        )
        self.db.add(self.user)
        self.db.flush()

        self.patient = Patient(
            id=uuid.uuid4(),
            user_id=self.user.id,
        )
        self.db.add(self.patient)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_build_patient_context_empty_records(self):
        service = MedicalQaService()
        context = service.build_patient_context(self.db, self.patient.id)
        self.assertIn("No uploaded clinical documents", context)

    def test_build_patient_context_with_comprehensive_records(self):
        # Add a Document
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            file_name="Lab_Report_2026.pdf",
            file_path="uploads/lab.pdf",
            document_type="lab_report",
            processing_status="completed",
            extracted_text="Patient fasting blood glucose: 105 mg/dL. HbA1c: 5.8%.",
            page_count=2,
        )
        self.db.add(doc)
        self.db.flush()

        # Add Medication & Prescription
        med = Medication(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            name="Metformin 500mg",
            normalized_name="metformin",
        )
        self.db.add(med)

        pres = Prescription(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            medication_id=med.id,
            document_id=doc.id,
            dosage="500 mg",
            frequency="twice daily",
            start_date=date(2026, 1, 15),
            instructions="take with meals",
        )
        self.db.add(pres)

        # Add Lab Result
        lab = LabResult(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            document_id=doc.id,
            test_name="Fasting Blood Glucose",
            value="105",
            unit="mg/dL",
            reference_range="70 - 99 mg/dL",
            result_date=date(2026, 2, 10),
        )
        self.db.add(lab)

        # Add Allergy
        allergy = Allergy(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            source_document_id=doc.id,
            medication_name="Penicillin",
            normalized_medication_name="penicillin",
            reaction="Hives",
            severity="moderate",
        )
        self.db.add(allergy)

        # Add Finding
        finding = Finding(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            finding_type="vital_sign",
            title="Mild Impaired Fasting Glucose",
            description="Fasting blood sugar slightly elevated",
            risk_level="low",
            recommendation="Monitor dietary carbohydrate intake",
        )
        self.db.add(finding)

        # Add Medical Event
        event = MedicalEvent(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            document_id=doc.id,
            event_type="consultation",
            event_date=date(2026, 1, 15),
            title="Endocrinology Checkup",
            description="Routine diabetes screening",
        )
        self.db.add(event)
        self.db.commit()

        service = MedicalQaService()
        context = service.build_patient_context(self.db, self.patient.id)

        self.assertIn("MEDICATIONS & PRESCRIPTIONS", context)
        self.assertIn("Metformin 500mg", context)
        self.assertIn("twice daily", context)
        self.assertIn("LABORATORY & BIOMARKER RESULTS", context)
        self.assertIn("Fasting Blood Glucose", context)
        self.assertIn("RECORDED ALLERGIES & ADVERSE REACTIONS", context)
        self.assertIn("Penicillin", context)
        self.assertIn("CLINICAL FINDINGS", context)
        self.assertIn("Mild Impaired Fasting Glucose", context)
        self.assertIn("MEDICAL EVENTS & TIMELINE", context)
        self.assertIn("Endocrinology Checkup", context)
        self.assertIn("UPLOADED DOCUMENTS & CLINICAL TEXT", context)
        self.assertIn("Lab_Report_2026.pdf", context)

    def test_patient_scoping_strict_isolation(self):
        # Create second patient B
        user_b = User(id=uuid.uuid4(), email="patient.b@example.com")
        self.db.add(user_b)
        self.db.flush()
        patient_b = Patient(id=uuid.uuid4(), user_id=user_b.id)
        self.db.add(patient_b)
        self.db.flush()

        # Add sensitive record to Patient B
        med_b = Medication(
            id=uuid.uuid4(),
            patient_id=patient_b.id,
            name="Confidential Med Beta",
            normalized_name="beta-med",
        )
        self.db.add(med_b)
        self.db.commit()

        service = MedicalQaService()
        context_a = service.build_patient_context(self.db, self.patient.id)

        # Patient A context MUST NOT contain Patient B's records
        self.assertNotIn("Confidential Med Beta", context_a)
        self.assertNotIn("beta-med", context_a)

    def test_answer_question_successful_flow(self):
        mock_provider = MockTestAIProvider(
            response_payload={
                "paragraphs": [
                    "Based on your prescription, you are taking Metformin 500mg twice daily with meals."
                ],
                "citations": [
                    {
                        "document_id": "doc-123",
                        "document_title": "Rx_2026.pdf",
                        "page": 1,
                        "quote": "Metformin 500mg BID",
                    }
                ],
                "confidence": 92,
                "guidance": "Answered strictly from your uploaded medical records.",
                "refusal": None,
                "cta": None,
            }
        )
        service = MedicalQaService(ai_provider=mock_provider)

        res = service.answer_question(
            db=self.db,
            patient=self.patient,
            question="What dose of Metformin am I taking?",
        )

        self.assertIsNotNone(res.id)
        self.assertEqual(res.role, "assistant")
        self.assertEqual(len(res.paragraphs), 1)
        self.assertIn("Metformin 500mg twice daily", res.paragraphs[0])
        self.assertEqual(len(res.citations), 1)
        self.assertEqual(res.citations[0].document_title, "Rx_2026.pdf")
        self.assertEqual(res.citations[0].quote, "Metformin 500mg BID")
        self.assertEqual(res.confidence, 92)
        self.assertIsNone(res.refusal)
        self.assertIsNone(res.cta)

        # Verify DB persistence of Question and AIAnalysis
        q_record = self.db.query(Question).filter(Question.patient_id == self.patient.id).first()
        self.assertIsNotNone(q_record)
        self.assertEqual(q_record.question, "What dose of Metformin am I taking?")

        analysis_record = (
            self.db.query(AIAnalysis)
            .filter(AIAnalysis.patient_id == self.patient.id)
            .filter(AIAnalysis.analysis_type == "qa")
            .first()
        )
        self.assertIsNotNone(analysis_record)
        self.assertEqual(analysis_record.question_id, q_record.id)
        self.assertEqual(analysis_record.confidence, 0.92)
        self.assertIn("paragraphs", dict(analysis_record.result or {}))

    def test_answer_question_safety_refusal(self):
        mock_provider = MockTestAIProvider(
            response_payload={
                "paragraphs": [
                    "I cannot diagnose new medical conditions. Please consult a qualified physician for evaluation."
                ],
                "citations": [],
                "confidence": 98,
                "guidance": "Clinical diagnosis requires direct medical examination.",
                "refusal": {
                    "overline": "NO DIAGNOSIS",
                    "headline": "Clinical diagnoses require direct physician evaluation",
                    "suggestions": [
                        "What symptoms were recorded in my last consultation?",
                        "What did my blood test results show?",
                    ],
                    "footnote": "This assistant explains recorded medical history and does not diagnose or prescribe.",
                },
                "cta": {
                    "label": "Find a healthcare provider nearby",
                    "note": "Consult a healthcare professional for clinical evaluation",
                },
            }
        )
        service = MedicalQaService(ai_provider=mock_provider)

        res = service.answer_question(
            db=self.db,
            patient=self.patient,
            question="Do I have diabetes based on these symptoms?",
        )

        self.assertIsNotNone(res.refusal)
        self.assertEqual(res.refusal.overline, "NO DIAGNOSIS")
        self.assertEqual(res.refusal.headline, "Clinical diagnoses require direct physician evaluation")
        self.assertEqual(len(res.refusal.suggestions), 2)
        self.assertIsNotNone(res.cta)
        self.assertEqual(res.cta.label, "Find a healthcare provider nearby")

    def test_answer_question_empty_validation_error(self):
        service = MedicalQaService()
        with self.assertRaises(HTTPException) as ctx:
            service.answer_question(self.db, self.patient, "   ")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_answer_question_ai_service_error_handling(self):
        mock_provider = MockTestAIProvider(exception_to_raise=AIServiceError("Gemini unavailable"))
        service = MedicalQaService(ai_provider=mock_provider)

        with self.assertRaises(HTTPException) as ctx:
            service.answer_question(self.db, self.patient, "What are my lab results?")
        self.assertEqual(ctx.exception.status_code, 503)

    def test_answer_question_rate_limit_error_handling(self):
        mock_provider = MockTestAIProvider(exception_to_raise=AIRateLimitError("Quota exceeded"))
        service = MedicalQaService(ai_provider=mock_provider)

        with self.assertRaises(HTTPException) as ctx:
            service.answer_question(self.db, self.patient, "What are my lab results?")
        self.assertEqual(ctx.exception.status_code, 429)

    def test_answer_question_auth_error_handling(self):
        mock_provider = MockTestAIProvider(exception_to_raise=AIAuthenticationError("Invalid API key"))
        service = MedicalQaService(ai_provider=mock_provider)

        with self.assertRaises(HTTPException) as ctx:
            service.answer_question(self.db, self.patient, "What are my lab results?")
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
