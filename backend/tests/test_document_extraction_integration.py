import unittest
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_application_user
from app.db.database import Base, get_db
from app.main import app
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
from app.schemas.extraction import MedicalExtractionResponse
from app.services.ai.mock_provider import MockAIProvider
from app.services.document_processing_service import (
    DocumentProcessingService,
    get_document_processing_service,
)
from app.services.document_processor import (
    DocumentProcessingResult,
    DocumentProcessor,
)
from app.services.medical_extraction_service import MedicalExtractionService
from app.services.medical_persistence_service import MedicalPersistenceService
from app.services.storage_service import (
    SupabaseStorageService,
    get_storage_service,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class DocumentExtractionIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()

        # Seed User A & Patient A
        self.user_a = User(
            id=uuid.uuid4(),
            email="user_a@example.com",
        )
        self.patient_a = Patient(
            id=uuid.uuid4(),
            user_id=self.user_a.id,
        )
        self.db.add_all([self.user_a, self.patient_a])
        self.db.commit()

        # Seed User B & Patient B
        self.user_b = User(
            id=uuid.uuid4(),
            email="user_b@example.com",
        )
        self.patient_b = Patient(
            id=uuid.uuid4(),
            user_id=self.user_b.id,
        )
        self.db.add_all([self.user_b, self.patient_b])
        self.db.commit()

        # Seed Document for Patient A
        self.doc_a = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a.id,
            file_name="patient_a_report.pdf",
            file_path="uploads/patient_a_report.pdf",
            document_type="prescription",
            processing_status="COMPLETED",
            extracted_text="Patient diagnosed with Acute Bronchitis. Rx: Amoxicillin 500mg PO TID x 10 days.",
            extraction_method="pymupdf",
            page_count=1,
        )
        self.db.add(self.doc_a)
        self.db.commit()

        # Mock Services
        self.mock_storage = MagicMock(spec=SupabaseStorageService)
        self.mock_storage.download_file.return_value = b"%PDF-1.4 dummy bytes"

        self.mock_processor = MagicMock(spec=DocumentProcessor)
        self.mock_processor.process_document.return_value = DocumentProcessingResult(
            extracted_text="Extracted text from processor",
            page_count=1,
            extraction_method="pymupdf",
            has_text=True,
        )

        self.mock_ai = MockAIProvider()
        self.extraction_service = MedicalExtractionService(ai_provider=self.mock_ai)
        self.persistence_service = MedicalPersistenceService()

        self.processing_service = DocumentProcessingService(
            storage_service=self.mock_storage,
            document_processor=self.mock_processor,
            medical_extraction_service=self.extraction_service,
            medical_persistence_service=self.persistence_service,
            db_session_factory=TestSessionLocal,
        )

        # Setup FastAPI TestClient with overrides
        self.current_test_user = self.user_a

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_get_user():
            return self.current_test_user

        def override_get_processing_service():
            return self.processing_service

        def override_get_storage():
            return self.mock_storage

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_application_user] = override_get_user
        app.dependency_overrides[get_document_processing_service] = override_get_processing_service
        app.dependency_overrides[get_storage_service] = override_get_storage

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.rollback()
        # Clean database
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

    def test_extract_user_document_success(self):
        response = self.client.post(f"/api/documents/{self.doc_a.id}/extract")
        assert response.status_code == 202

        data = response.json()
        assert data["document_id"] == str(self.doc_a.id)
        assert data["patient_id"] == str(self.patient_a.id)
        assert data["status"] in ["PROCESSING", "COMPLETED"]

        # Check records in DB
        meds = self.db.query(Medication).filter(Medication.patient_id == self.patient_a.id).all()
        assert len(meds) >= 1

        prescriptions = self.db.query(Prescription).filter(Prescription.patient_id == self.patient_a.id).all()
        assert len(prescriptions) >= 1

        analyses = self.db.query(AIAnalysis).filter(AIAnalysis.patient_id == self.patient_a.id).all()
        assert len(analyses) == 1

    def test_extract_tenant_isolation_forbidden(self):
        # User B attempting to extract User A's document
        self.current_test_user = self.user_b
        response = self.client.post(f"/api/documents/{self.doc_a.id}/extract")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_extract_nonexistent_document(self):
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/documents/{fake_id}/extract")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_extract_unprocessed_document_triggers_text_pipeline_first(self):
        # Document uploaded but not yet processed
        unprocessed_doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a.id,
            file_name="unprocessed.pdf",
            file_path="uploads/unprocessed.pdf",
            document_type="prescription",
            processing_status="UPLOADED",
            extracted_text=None,
        )
        self.db.add(unprocessed_doc)
        self.db.commit()

        response = self.client.post(f"/api/documents/{unprocessed_doc.id}/extract")
        assert response.status_code == 202

        # Should have called download and processor
        self.mock_storage.download_file.assert_called()
        self.mock_processor.process_document.assert_called()

        self.db.refresh(unprocessed_doc)
        assert unprocessed_doc.processing_status == "COMPLETED"
        assert unprocessed_doc.extracted_text is not None

    def test_extract_document_with_malformed_lab_date_persists_as_null(self):
        # Configure mock AI provider to return a lab result with malformed date "200X-07-07"
        self.mock_ai.canned_structured_response = {
            "document_type_detected": "lab_report",
            "summary": "Laboratory metabolic panel.",
            "confidence_score": 0.95,
            "events": [],
            "medications": [],
            "lab_results": [
                {
                    "test_name": "Hemoglobin A1c",
                    "value": "6.5",
                    "unit": "%",
                    "reference_range": "< 5.7%",
                    "result_date": "200X-07-07",
                }
            ],
            "allergies": [],
            "findings": [],
        }

        response = self.client.post(f"/api/documents/{self.doc_a.id}/extract")
        assert response.status_code == 202, f"Expected 202 Accepted but got {response.status_code}: {response.text}"

        data = response.json()
        assert data["document_id"] == str(self.doc_a.id)
        assert data["patient_id"] == str(self.patient_a.id)

        # Verify DB persistence
        db_labs = self.db.query(LabResult).filter(LabResult.patient_id == self.patient_a.id).all()
        assert len(db_labs) == 1
        assert db_labs[0].test_name == "Hemoglobin A1c"
        assert db_labs[0].value == "6.5"
        assert db_labs[0].unit == "%"
        assert db_labs[0].result_date is None
        assert db_labs[0].document_id == self.doc_a.id

    def test_extract_endpoint_re_extraction_is_idempotent(self):
        # 1. First extraction call
        resp1 = self.client.post(f"/api/documents/{self.doc_a.id}/extract")
        assert resp1.status_code == 202

        # 2. Query /api/records/analyses -> Expect 1 record
        analyses_resp1 = self.client.get("/api/records/analyses")
        assert analyses_resp1.status_code == 200
        analyses_data1 = analyses_resp1.json()
        assert len(analyses_data1) == 1
        assert analyses_data1[0]["result"]["document_id"] == str(self.doc_a.id)

        # 3. Trigger extraction AGAIN for same document
        resp2 = self.client.post(f"/api/documents/{self.doc_a.id}/extract")
        assert resp2.status_code == 202

        # 4. Query /api/records/analyses AGAIN -> Expect STILL 1 record!
        analyses_resp2 = self.client.get("/api/records/analyses")
        assert analyses_resp2.status_code == 200
        analyses_data2 = analyses_resp2.json()
        assert len(analyses_data2) == 1  # No duplicate row created!
        assert analyses_data2[0]["result"]["document_id"] == str(self.doc_a.id)

    def test_extract_synthetic_lab_report_pipeline_and_api(self):
        # Configure mock AI to return synthetic lab report entities
        self.mock_ai.canned_structured_response = {
            "document_type_detected": "lab_report",
            "summary": "Synthetic lab report showing elevated Fasting Blood Glucose.",
            "confidence_score": 0.96,
            "events": [
                {
                    "event_type": "lab_test",
                    "title": "Comprehensive Metabolic Panel",
                    "description": "Routine blood chemistry evaluation.",
                    "event_date": "2026-08-10",
                }
            ],
            "medications": [],
            "lab_results": [
                {
                    "test_name": "Fasting Blood Glucose",
                    "value": "135",
                    "unit": "mg/dL",
                    "reference_range": "70-99 mg/dL",
                    "result_date": "2026-08-10",
                },
                {
                    "test_name": "Hemoglobin A1c",
                    "value": "6.4",
                    "unit": "%",
                    "reference_range": "< 5.7%",
                    "result_date": "2026-08-10",
                },
            ],
            "allergies": [],
            "findings": [
                {
                    "finding_type": "vital_sign",
                    "title": "Elevated Blood Glucose",
                    "description": "Fasting glucose measured at 135 mg/dL.",
                    "risk_level": "medium",
                    "confidence": 0.95,
                }
            ],
        }

        # 1. Post to extract endpoint
        extract_resp = self.client.post(f"/api/documents/{self.doc_a.id}/extract")
        assert extract_resp.status_code == 202

        # 2. Query /api/records/lab-results API
        lab_resp = self.client.get("/api/records/lab-results")
        assert lab_resp.status_code == 200
        labs = lab_resp.json()
        assert len(labs) == 2
        assert labs[0]["test_name"] in ["Fasting Blood Glucose", "Hemoglobin A1c"]
        assert labs[0]["source_document_id"] == str(self.doc_a.id)

    def test_extract_synthetic_allergy_report_pipeline_and_api(self):
        # Configure mock AI to return synthetic allergy document entities
        self.mock_ai.canned_structured_response = {
            "document_type_detected": "consultation_note",
            "summary": "Patient clinical consultation noting documented severe allergy to Penicillin.",
            "confidence_score": 0.94,
            "events": [
                {
                    "event_type": "consultation",
                    "title": "Allergy Evaluation Visit",
                    "description": "Consultation regarding drug allergy history.",
                    "event_date": None,
                }
            ],
            "medications": [],
            "lab_results": [],
            "allergies": [
                {
                    "medication_name": "Penicillin V",
                    "normalized_medication_name": "penicillin v",
                    "reaction": "Anaphylactic hives and shortness of breath",
                    "severity": "severe",
                }
            ],
            "findings": [],
        }

        # 1. Post to extract endpoint
        extract_resp = self.client.post(f"/api/documents/{self.doc_a.id}/extract")
        assert extract_resp.status_code == 202

        # 2. Query /api/records/allergies API
        allergies_resp = self.client.get("/api/records/allergies")
        assert allergies_resp.status_code == 200
        allergies = allergies_resp.json()
        assert len(allergies) == 1
        assert allergies[0]["medication_name"] == "Penicillin V"
        assert allergies[0]["severity"] == "severe"
        assert allergies[0]["source_document_id"] == str(self.doc_a.id)

    def test_duplicate_extraction_job_prevention(self):
        # Test active extraction registration lock prevents concurrent execution
        doc_id = self.doc_a.id
        registered = self.processing_service.register_active_extraction(doc_id)
        assert registered is True

        # Second attempt must return False
        duplicate_registered = self.processing_service.register_active_extraction(doc_id)
        assert duplicate_registered is False

        # Endpoint call while active returns 202 with active status
        resp = self.client.post(f"/api/documents/{doc_id}/extract")
        assert resp.status_code == 202

        self.processing_service.unregister_active_extraction(doc_id)
        assert self.processing_service.is_extraction_active(doc_id) is False
