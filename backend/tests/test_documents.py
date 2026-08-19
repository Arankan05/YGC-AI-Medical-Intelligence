import io
import time
import unittest
import uuid
from unittest.mock import MagicMock, patch

import jwt
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
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
from app.services.document_processing_service import (
    DocumentProcessingService,
    get_document_processing_service,
)
from app.services.document_processor import (
    DocumentProcessingResult,
    DocumentProcessor,
)
from app.services.storage_service import (
    StorageDeleteError,
    StorageDownloadError,
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

TEST_JWT_SECRET = "test-secret-key-for-documents-api-testing-32bytes"


def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL="sqlite:///:memory:",
        SUPABASE_URL="https://mockproject.supabase.co",
        SUPABASE_KEY="mock-anon-key-12345",
        SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
        SUPABASE_JWT_ALGORITHM="HS256",
        SUPABASE_JWT_AUDIENCE="authenticated",
    )


class DocumentsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()
        self.settings = get_test_settings()

        # Create mock storage service
        self.mock_storage_service = MagicMock(spec=SupabaseStorageService)
        self.mock_storage_service.upload_file.return_value = "mock/storage/path.pdf"
        self.mock_storage_service.delete_file.return_value = True
        self.mock_storage_service.download_file.return_value = b"%PDF-1.4 mock pdf content"

        # Create mock document processor
        self.mock_document_processor = MagicMock(spec=DocumentProcessor)
        self.mock_document_processor.process_document.return_value = DocumentProcessingResult(
            extracted_text="--- Page 1 ---\nTest Extracted Clinical Text",
            page_count=1,
            extraction_method="pymupdf",
            has_text=True,
            page_texts=["Test Extracted Clinical Text"],
            confidence=None,
        )

        # Create processing service with mocks
        self.processing_service = DocumentProcessingService(
            storage_service=self.mock_storage_service,
            document_processor=self.mock_document_processor,
        )

        # User A and Patient A
        self.user_a_id = uuid.uuid4()
        self.user_a_email = "user_a@example.com"
        self.user_a = User(id=self.user_a_id, email=self.user_a_email)
        self.db.add(self.user_a)

        self.patient_a_id = uuid.uuid4()
        self.patient_a = Patient(id=self.patient_a_id, user_id=self.user_a_id)
        self.db.add(self.patient_a)

        # User B and Patient B
        self.user_b_id = uuid.uuid4()
        self.user_b_email = "user_b@example.com"
        self.user_b = User(id=self.user_b_id, email=self.user_b_email)
        self.db.add(self.user_b)

        self.patient_b_id = uuid.uuid4()
        self.patient_b = Patient(id=self.patient_b_id, user_id=self.user_b_id)
        self.db.add(self.patient_b)

        # User without Patient
        self.user_no_patient_id = uuid.uuid4()
        self.user_no_patient_email = "nopatient@example.com"
        self.user_no_patient = User(id=self.user_no_patient_id, email=self.user_no_patient_email)
        self.db.add(self.user_no_patient)

        self.db.commit()

        # FastAPI dependency overrides
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_get_settings():
            return self.settings

        def override_get_storage():
            return self.mock_storage_service

        def override_get_processing_service():
            return self.processing_service

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = override_get_settings
        app.dependency_overrides[get_storage_service] = override_get_storage
        app.dependency_overrides[get_document_processing_service] = override_get_processing_service

        self.client = TestClient(app)

    def tearDown(self):
        self.db.query(Document).delete()
        self.db.query(Patient).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()
        app.dependency_overrides.clear()

    def _create_token(
        self,
        sub: str,
        email: str,
        secret: str = TEST_JWT_SECRET,
        expires_in: int = 3600,
    ) -> str:
        payload = {
            "sub": sub,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_in,
        }
        return jwt.encode(payload, secret, algorithm="HS256")

    # =========================================================================
    # 1. Unauthenticated / Authentication Tests
    # =========================================================================

    def test_upload_unauthenticated(self):
        """Unauthenticated requests to upload endpoint must receive HTTP 401."""
        response = self.client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_unauthenticated(self):
        """Unauthenticated requests to list endpoint must receive HTTP 401."""
        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_document_unauthenticated(self):
        """Unauthenticated requests to get document must receive HTTP 401."""
        doc_id = uuid.uuid4()
        response = self.client.get(f"/api/documents/{doc_id}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_document_unauthenticated(self):
        """Unauthenticated requests to delete document must receive HTTP 401."""
        doc_id = uuid.uuid4()
        response = self.client.delete(f"/api/documents/{doc_id}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # =========================================================================
    # 2. Patient Ownership & Profile Verification Tests
    # =========================================================================

    def test_upload_fails_when_user_has_no_patient_record(self):
        """Authenticated user without an associated Patient profile receives HTTP 404."""
        token = self._create_token(
            sub=str(self.user_no_patient_id),
            email=self.user_no_patient_email,
        )
        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("report.pdf", b"%PDF-1.4 sample content", "application/pdf")},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("patient profile", response.json()["detail"].lower())

    # =========================================================================
    # 3. File Validation Tests
    # =========================================================================

    def test_upload_empty_file_rejected(self):
        """Empty files must be rejected with HTTP 400."""
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("empty", response.json()["detail"].lower())

    def test_upload_unsupported_file_type_rejected(self):
        """Files with unsupported content (e.g. text/plain or executable) receive HTTP 400."""
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.txt", b"plain text content", "text/plain")},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unsupported", response.json()["detail"].lower())

    def test_upload_spoofed_extension_rejected(self):
        """File claiming to be .pdf but containing plain text fails magic-byte verification."""
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("fake.pdf", b"This is not a pdf file", "application/pdf")},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_mismatched_extension_and_content_rejected(self):
        """Valid PNG content uploaded with .pdf extension receives HTTP 400."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("image.pdf", png_bytes, "application/pdf")},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("extension", response.json()["detail"].lower())

    def test_upload_oversized_file_rejected(self):
        """Files exceeding 25 MB must be rejected with HTTP 413."""
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        # Mock file size > 25MB by patching len check or sending oversized payload
        with patch("app.api.documents.MAX_FILE_SIZE_BYTES", 100):
            response = self.client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("large.pdf", b"%PDF-1.4" + b"X" * 150, "application/pdf")},
            )
            self.assertEqual(response.status_code, status.HTTP_413_CONTENT_TOO_LARGE)
            self.assertIn("exceeds", response.json()["detail"].lower())

    # =========================================================================
    # 4. Successful Upload Tests
    # =========================================================================

    def test_upload_pdf_success(self):
        """Valid PDF upload returns 201 and stores record with initial status 'UPLOADED'."""
        pdf_bytes = b"%PDF-1.4 header and sample document bytes"
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)

        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"document_type": "lab_report"},
            files={"file": ("blood_test.pdf", pdf_bytes, "application/pdf")},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data["file_name"], "blood_test.pdf")
        self.assertEqual(data["document_type"], "lab_report")
        self.assertEqual(data["processing_status"], "UPLOADED")
        self.assertEqual(data["patient_id"], str(self.patient_a_id))
        self.assertIn(str(self.user_a_id), data["file_path"])
        self.assertIn(str(self.patient_a_id), data["file_path"])
        self.assertTrue(self.mock_storage_service.upload_file.called)

    def test_upload_png_image_success(self):
        """Valid PNG upload succeeds and defaults document_type to 'unknown' when unspecified."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)

        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("xray.png", png_bytes, "image/png")},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["file_name"], "xray.png")
        self.assertEqual(data["document_type"], "unknown")
        self.assertEqual(data["processing_status"], "UPLOADED")

    def test_upload_jpeg_image_success(self):
        """Valid JPEG upload succeeds with prescription type."""
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 30
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)

        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"document_type": "prescription"},
            files={"file": ("rx_sheet.jpeg", jpeg_bytes, "image/jpeg")},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["document_type"], "prescription")
        self.assertEqual(data["processing_status"], "UPLOADED")

    def test_upload_path_traversal_sanitized(self):
        """Filename with path traversal sequences is sanitized before storage."""
        pdf_bytes = b"%PDF-1.4 malicious path test"
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)

        response = self.client.post(
            "/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("../../etc/passwd/report.pdf", pdf_bytes, "application/pdf")},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["file_name"], "report.pdf")
        self.assertNotIn("..", data["file_path"])

    # =========================================================================
    # 5. List Documents Tests & Tenant Isolation
    # =========================================================================

    def test_list_documents_only_returns_current_user_documents(self):
        """Listing documents returns only records for the authenticated user's patient."""
        # Create doc for User A
        doc_a = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a_id,
            file_name="doc_a.pdf",
            file_path=f"{self.user_a_id}/{self.patient_a_id}/doc_a.pdf",
            document_type="prescription",
            processing_status="UPLOADED",
        )
        self.db.add(doc_a)

        # Create doc for User B
        doc_b = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_b_id,
            file_name="doc_b.pdf",
            file_path=f"{self.user_b_id}/{self.patient_b_id}/doc_b.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc_b)
        self.db.commit()

        token_a = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        res_a = self.client.get("/api/documents", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        data_a = res_a.json()
        self.assertEqual(data_a["total"], 1)
        self.assertEqual(data_a["items"][0]["id"], str(doc_a.id))
        self.assertEqual(data_a["items"][0]["file_name"], "doc_a.pdf")

        # User B check
        token_b = self._create_token(sub=str(self.user_b_id), email=self.user_b_email)
        res_b = self.client.get("/api/documents", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        data_b = res_b.json()
        self.assertEqual(data_b["total"], 1)
        self.assertEqual(data_b["items"][0]["id"], str(doc_b.id))
        self.assertEqual(data_b["items"][0]["file_name"], "doc_b.pdf")

    # =========================================================================
    # 6. Get Document Tests & Ownership Verification
    # =========================================================================

    def test_get_own_document_success(self):
        """Authenticated user can fetch metadata for their own document."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a_id,
            file_name="my_report.pdf",
            file_path=f"{self.user_a_id}/{self.patient_a_id}/my_report.pdf",
            document_type="medical_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.get(
            f"/api/documents/{doc.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], str(doc.id))
        self.assertEqual(data["file_name"], "my_report.pdf")

    def test_get_nonexistent_document_returns_404(self):
        """Fetching a non-existent document ID returns HTTP 404."""
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.get(
            f"/api/documents/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_other_user_document_returns_403(self):
        """Attempting to get another user's document returns HTTP 403 Forbidden."""
        doc_b = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_b_id,
            file_name="b_private.pdf",
            file_path=f"{self.user_b_id}/{self.patient_b_id}/b_private.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc_b)
        self.db.commit()

        token_a = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.get(
            f"/api/documents/{doc_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # =========================================================================
    # 7. Delete Document Tests & Consistency Handling
    # =========================================================================

    def test_delete_own_document_success(self):
        """Deleting own document deletes from storage and database."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a_id,
            file_name="to_delete.pdf",
            file_path=f"{self.user_a_id}/{self.patient_a_id}/to_delete.pdf",
            document_type="prescription",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.delete(
            f"/api/documents/{doc.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], str(doc.id))
        self.mock_storage_service.delete_file.assert_called_once_with(doc.file_path)

        # Ensure DB record is removed
        remaining = self.db.query(Document).filter(Document.id == doc.id).first()
        self.assertIsNone(remaining)

    def test_delete_other_user_document_forbidden(self):
        """Attempting to delete another user's document returns HTTP 403."""
        doc_b = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_b_id,
            file_name="b_doc.pdf",
            file_path=f"{self.user_b_id}/{self.patient_b_id}/b_doc.pdf",
            document_type="prescription",
            processing_status="UPLOADED",
        )
        self.db.add(doc_b)
        self.db.commit()

        token_a = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.delete(
            f"/api/documents/{doc_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify DB record was NOT deleted
        self.assertIsNotNone(self.db.query(Document).filter(Document.id == doc_b.id).first())

    def test_delete_storage_failure_preserves_db_record(self):
        """If storage deletion fails, DB record is NOT deleted and HTTP 500 is returned."""
        self.mock_storage_service.delete_file.side_effect = StorageDeleteError("Storage connection failed")

        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a_id,
            file_name="persist_on_fail.pdf",
            file_path=f"{self.user_a_id}/{self.patient_a_id}/persist_on_fail.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.delete(
            f"/api/documents/{doc.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Ensure DB record is still preserved
        preserved = self.db.query(Document).filter(Document.id == doc.id).first()
        self.assertIsNotNone(preserved)

    def test_upload_db_failure_cleans_up_storage(self):
        """If DB commit fails during upload, uploaded storage file is deleted to avoid orphaned files."""
        pdf_bytes = b"%PDF-1.4 sample content"
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)

        with patch.object(self.db, "commit", side_effect=Exception("Simulated DB connection drop")):
            response = self.client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("rollback_test.pdf", pdf_bytes, "application/pdf")},
            )
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            # Verify cleanup deletion was called
            self.assertTrue(self.mock_storage_service.delete_file.called)

    # =========================================================================
    # 8. Process Document Tests (Orchestration & Ownership)
    # =========================================================================

    def test_process_unauthenticated(self):
        """Unauthenticated requests to process endpoint receive HTTP 401."""
        doc_id = uuid.uuid4()
        response = self.client.post(f"/api/documents/{doc_id}/process")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_process_own_text_document_success(self):
        """Authenticated user can process their own document successfully via PyMuPDF."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a_id,
            file_name="lab_cbc.pdf",
            file_path=f"{self.user_a_id}/{self.patient_a_id}/lab_cbc.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            f"/api/documents/{doc.id}/process",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["document_id"], str(doc.id))
        self.assertEqual(data["processing_status"], "COMPLETED")
        self.assertEqual(data["extraction_method"], "pymupdf")
        self.assertTrue(data["has_text"])
        self.assertIn("Clinical Text", data["extracted_text"])
        self.assertEqual(data["page_count"], 1)

        # Verify DB updated
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "COMPLETED")
        self.assertEqual(doc.extracted_text, "--- Page 1 ---\nTest Extracted Clinical Text")
        self.assertEqual(doc.extraction_method, "pymupdf")
        self.assertEqual(doc.page_count, 1)
        self.assertIsNotNone(doc.processed_at)

    def test_process_own_scanned_document_success_ocr(self):
        """Authenticated user processing a scanned document receives OCR results and 200."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a_id,
            file_name="scanned_report.pdf",
            file_path=f"{self.user_a_id}/{self.patient_a_id}/scanned_report.pdf",
            document_type="prescription",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        self.mock_document_processor.process_document.return_value = DocumentProcessingResult(
            extracted_text="--- Page 1 ---\nScanned Prescription: Metformin 500mg",
            page_count=1,
            extraction_method="tesseract",
            has_text=True,
            page_texts=["Scanned Prescription: Metformin 500mg"],
            confidence=91.0,
        )

        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            f"/api/documents/{doc.id}/process",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["extraction_method"], "tesseract")
        self.assertEqual(data["confidence"], 91.0)
        self.assertEqual(data["processing_status"], "COMPLETED")

        # Verify DB updated
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "COMPLETED")
        self.assertEqual(doc.extracted_text, "--- Page 1 ---\nScanned Prescription: Metformin 500mg")
        self.assertEqual(doc.extraction_method, "tesseract")
        self.assertEqual(doc.page_count, 1)
        self.assertIsNotNone(doc.processed_at)


    def test_process_other_user_document_forbidden(self):
        """User A attempting to process User B's document receives HTTP 403 Forbidden."""
        doc_b = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_b_id,
            file_name="b_doc.pdf",
            file_path=f"{self.user_b_id}/{self.patient_b_id}/b_doc.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc_b)
        self.db.commit()

        token_a = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            f"/api/documents/{doc_b.id}/process",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_process_nonexistent_document_returns_404(self):
        """Processing non-existent document ID returns HTTP 404."""
        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            f"/api/documents/{uuid.uuid4()}/process",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_process_storage_failure_returns_500(self):
        """If storage download fails, endpoint returns 500 and marks document as FAILED."""
        self.mock_storage_service.download_file.side_effect = StorageDownloadError("Download failed")

        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a_id,
            file_name="fail_doc.pdf",
            file_path=f"{self.user_a_id}/{self.patient_a_id}/fail_doc.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        token = self._create_token(sub=str(self.user_a_id), email=self.user_a_email)
        response = self.client.post(
            f"/api/documents/{doc.id}/process",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "FAILED")
        self.assertIsNotNone(doc.error_message)


if __name__ == "__main__":
    unittest.main()

