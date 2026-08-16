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
        assert response.status_code == 200

        data = response.json()
        assert data["document_id"] == str(self.doc_a.id)
        assert data["patient_id"] == str(self.patient_a.id)
        assert data["status"] == "COMPLETED"
        assert "extracted_record" in data
        assert len(data["extracted_record"]["medications"]) > 0
        assert data["persisted_counts"]["medications"] >= 1

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
        assert response.status_code == 200

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
        assert response.status_code == 200, f"Expected 200 OK but got {response.status_code}: {response.text}"

        data = response.json()
        assert data["document_id"] == str(self.doc_a.id)
        assert data["patient_id"] == str(self.patient_a.id)
        assert data["status"] == "COMPLETED"
        assert len(data["extracted_record"]["lab_results"]) == 1
        assert data["extracted_record"]["lab_results"][0]["test_name"] == "Hemoglobin A1c"
        assert data["extracted_record"]["lab_results"][0]["value"] == "6.5"
        assert data["extracted_record"]["lab_results"][0]["unit"] == "%"
        assert data["extracted_record"]["lab_results"][0]["result_date"] is None
        assert data["persisted_counts"]["lab_results"] == 1

        # Verify DB persistence
        db_labs = self.db.query(LabResult).filter(LabResult.patient_id == self.patient_a.id).all()
        assert len(db_labs) == 1
        assert db_labs[0].test_name == "Hemoglobin A1c"
        assert db_labs[0].value == "6.5"
        assert db_labs[0].unit == "%"
        assert db_labs[0].result_date is None
        assert db_labs[0].document_id == self.doc_a.id

