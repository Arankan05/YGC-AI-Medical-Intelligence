import unittest
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.document import Document
from app.models.patient import Patient
from app.models.user import User
from app.services.document_processing_service import (
    DocumentProcessResult,
    DocumentProcessingService,
)
from app.services.document_processor import (
    DocumentProcessingError,
    DocumentProcessingResult,
    DocumentProcessor,
)
from app.services.pdf_extractor import InvalidPDFError
from app.services.storage_service import (
    StorageDownloadError,
    SupabaseStorageService,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class DocumentProcessingServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()

        # Mock dependencies
        self.mock_storage = MagicMock(spec=SupabaseStorageService)
        self.mock_processor = MagicMock(spec=DocumentProcessor)

        self.service = DocumentProcessingService(
            storage_service=self.mock_storage,
            document_processor=self.mock_processor,
        )

        # User A & Patient A
        self.user_a = User(id=uuid.uuid4(), email="user_a@example.com")
        self.db.add(self.user_a)
        self.patient_a = Patient(id=uuid.uuid4(), user_id=self.user_a.id)
        self.db.add(self.patient_a)

        # User B & Patient B
        self.user_b = User(id=uuid.uuid4(), email="user_b@example.com")
        self.db.add(self.user_b)
        self.patient_b = Patient(id=uuid.uuid4(), user_id=self.user_b.id)
        self.db.add(self.patient_b)

        # User without Patient
        self.user_no_patient = User(id=uuid.uuid4(), email="nopatient@example.com")
        self.db.add(self.user_no_patient)

        self.db.commit()

    def tearDown(self):
        self.db.query(Document).delete()
        self.db.query(Patient).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_process_text_pdf_success_pymupdf(self):
        """Test successful processing of a text-based PDF via PyMuPDF."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a.id,
            file_name="lab_report.pdf",
            file_path=f"{self.user_a.id}/{self.patient_a.id}/lab_report.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        self.mock_storage.download_file.return_value = b"%PDF-1.4 mock text pdf content"
        self.mock_processor.process_document.return_value = DocumentProcessingResult(
            extracted_text="--- Page 1 ---\nHemoglobin: 14.2 g/dL",
            page_count=1,
            extraction_method="pymupdf",
            has_text=True,
            page_texts=["Hemoglobin: 14.2 g/dL"],
            confidence=None,
        )

        result = self.service.process_user_document(
            user=self.user_a,
            document_id=uuid.UUID(str(doc.id)),
            db=self.db,
        )

        self.assertIsInstance(result, DocumentProcessResult)
        self.assertEqual(result.processing_status, "COMPLETED")
        self.assertEqual(result.extraction_method, "pymupdf")
        self.assertEqual(result.page_count, 1)
        self.assertTrue(result.has_text)
        self.assertIn("Hemoglobin", result.extracted_text)
        self.assertIsNone(result.confidence)

        # Check updated DB record
        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "COMPLETED")
        self.assertEqual(doc.extracted_text, result.extracted_text)
        self.assertEqual(doc.extraction_method, "pymupdf")
        self.assertEqual(doc.page_count, 1)
        self.assertIsNotNone(doc.processed_at)
        self.assertIsNone(doc.error_message)

    def test_process_scanned_pdf_success_tesseract(self):
        """Test successful processing of a scanned image PDF via Tesseract OCR."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a.id,
            file_name="scanned_rx.pdf",
            file_path=f"{self.user_a.id}/{self.patient_a.id}/scanned_rx.pdf",
            document_type="prescription",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        self.mock_storage.download_file.return_value = b"%PDF-1.4 mock scanned pdf"
        self.mock_processor.process_document.return_value = DocumentProcessingResult(
            extracted_text="--- Page 1 ---\nAmoxicillin 500mg PO TID",
            page_count=1,
            extraction_method="tesseract",
            has_text=True,
            page_texts=["Amoxicillin 500mg PO TID"],
            confidence=94.5,
        )

        result = self.service.process_user_document(
            user=self.user_a,
            document_id=uuid.UUID(str(doc.id)),
            db=self.db,
        )

        self.assertEqual(result.processing_status, "COMPLETED")
        self.assertEqual(result.extraction_method, "tesseract")
        self.assertEqual(result.confidence, 94.5)

        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "COMPLETED")
        self.assertEqual(doc.extracted_text, result.extracted_text)
        self.assertEqual(doc.extraction_method, "tesseract")
        self.assertEqual(doc.page_count, 1)
        self.assertIsNotNone(doc.processed_at)
        self.assertIsNone(doc.error_message)


    def test_process_other_user_document_forbidden(self):
        """User A cannot process User B's document (returns 403 Forbidden)."""
        doc_b = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_b.id,
            file_name="b_private.pdf",
            file_path=f"{self.user_b.id}/{self.patient_b.id}/b_private.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc_b)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            self.service.process_user_document(
                user=self.user_a,
                document_id=uuid.UUID(str(doc_b.id)),
                db=self.db,
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.mock_storage.download_file.assert_not_called()
        self.mock_processor.process_document.assert_not_called()

    def test_process_nonexistent_document_not_found(self):
        """Processing non-existent document ID returns 404 Not Found."""
        with self.assertRaises(HTTPException) as ctx:
            self.service.process_user_document(
                user=self.user_a,
                document_id=uuid.uuid4(),
                db=self.db,
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_process_user_without_patient_profile_not_found(self):
        """User without a patient profile receives 404 Not Found."""
        with self.assertRaises(HTTPException) as ctx:
            self.service.process_user_document(
                user=self.user_no_patient,
                document_id=uuid.uuid4(),
                db=self.db,
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_storage_download_failure_marks_document_failed(self):
        """If storage download fails, document status is set to FAILED with safe error message."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a.id,
            file_name="lost_file.pdf",
            file_path=f"{self.user_a.id}/{self.patient_a.id}/lost_file.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        self.mock_storage.download_file.side_effect = StorageDownloadError("File not found in bucket")

        with self.assertRaises(HTTPException) as ctx:
            self.service.process_user_document(
                user=self.user_a,
                document_id=uuid.UUID(str(doc.id)),
                db=self.db,
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "FAILED")
        self.assertIsNotNone(doc.error_message)
        self.assertIn("storage", doc.error_message.lower())
        self.assertIsNone(doc.extracted_text)
        self.assertIsNone(doc.extraction_method)
        self.assertIsNone(doc.page_count)

    def test_invalid_pdf_marks_document_failed(self):
        """If PDF is corrupt or invalid, document status is set to FAILED and HTTP 422 returned."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a.id,
            file_name="corrupt.pdf",
            file_path=f"{self.user_a.id}/{self.patient_a.id}/corrupt.pdf",
            document_type="lab_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        self.mock_storage.download_file.return_value = b"Not a valid pdf"
        self.mock_processor.process_document.side_effect = InvalidPDFError("Corrupt PDF bytes")

        with self.assertRaises(HTTPException) as ctx:
            self.service.process_user_document(
                user=self.user_a,
                document_id=uuid.UUID(str(doc.id)),
                db=self.db,
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "FAILED")
        self.assertIsNotNone(doc.error_message)
        self.assertIsNone(doc.extracted_text)
        self.assertIsNone(doc.extraction_method)
        self.assertIsNone(doc.page_count)

    def test_unexpected_processing_failure_marks_document_failed(self):
        """If processing encounters unexpected error, document status is set to FAILED."""
        doc = Document(
            id=uuid.uuid4(),
            patient_id=self.patient_a.id,
            file_name="error_doc.pdf",
            file_path=f"{self.user_a.id}/{self.patient_a.id}/error_doc.pdf",
            document_type="medical_report",
            processing_status="UPLOADED",
        )
        self.db.add(doc)
        self.db.commit()

        self.mock_storage.download_file.return_value = b"%PDF-1.4 content"
        self.mock_processor.process_document.side_effect = DocumentProcessingError("Extractor crashed")

        with self.assertRaises(HTTPException) as ctx:
            self.service.process_user_document(
                user=self.user_a,
                document_id=uuid.UUID(str(doc.id)),
                db=self.db,
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.db.refresh(doc)
        self.assertEqual(doc.processing_status, "FAILED")
        self.assertIsNotNone(doc.error_message)
        self.assertIsNone(doc.extracted_text)
        self.assertIsNone(doc.extraction_method)
        self.assertIsNone(doc.page_count)




if __name__ == "__main__":
    unittest.main()
