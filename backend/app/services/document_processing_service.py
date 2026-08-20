import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.patient import Patient
from app.models.user import User
from app.schemas.extraction import MedicalExtractionResponse
from app.services.ai.base_provider import AIServiceError
from app.services.document_processor import (
    DocumentProcessingError,
    DocumentProcessingResult,
    DocumentProcessor,
    get_document_processor,
)
from app.services.medical_extraction_service import (
    MedicalExtractionService,
    get_medical_extraction_service,
)
from app.services.medical_persistence_service import (
    MedicalPersistenceService,
    get_medical_persistence_service,
)
from app.services.ocr_service import OCRError
from app.services.pdf_extractor import InvalidPDFError
from app.services.storage_service import (
    StorageError,
    SupabaseStorageService,
    get_storage_service,
)

logger = logging.getLogger(__name__)

_active_extractions: set[UUID] = set()
_active_extractions_lock = threading.Lock()


@dataclass(frozen=True)
class DocumentProcessResult:
    """
    Structured outcome of processing an uploaded document record.

    Attributes:
        document_id: UUID of the processed document.
        patient_id: UUID of the owning patient.
        file_name: Original sanitized filename.
        processing_status: Final processing lifecycle status ('COMPLETED' or 'FAILED').
        extracted_text: Extracted text with page boundaries.
        page_count: Total pages processed.
        extraction_method: Strategy used ('pymupdf' or 'tesseract').
        has_text: True if text was extracted, False otherwise.
        confidence: Average OCR confidence score if OCR was used, else None.
        processed_at: Timestamp when processing completed.
    """
    document_id: UUID
    patient_id: UUID
    file_name: str
    processing_status: str
    extracted_text: str
    page_count: int
    extraction_method: str
    has_text: bool
    confidence: Optional[float] = None
    processed_at: Optional[datetime] = None


class DocumentProcessingService:
    """
    Service responsible for orchestrating end-to-end document processing for an authenticated user:
    1. Verifies patient profile and document ownership isolation.
    2. Downloads private document binary content from Supabase Storage.
    3. Executes text extraction via DocumentProcessor (PyMuPDF with Tesseract OCR fallback).
    4. Updates database processing_status, processed_at, and error_message.
    5. Optionally extracts and persists structured clinical entities via MedicalExtractionService and MedicalPersistenceService.
    """

    def __init__(
        self,
        storage_service: Optional[SupabaseStorageService] = None,
        document_processor: Optional[DocumentProcessor] = None,
        medical_extraction_service: Optional[MedicalExtractionService] = None,
        medical_persistence_service: Optional[MedicalPersistenceService] = None,
        db_session_factory: Optional[Any] = None,
    ):
        self._storage_service = storage_service
        self._document_processor = document_processor
        self._medical_extraction_service = medical_extraction_service
        self._medical_persistence_service = medical_persistence_service
        self._db_session_factory = db_session_factory

    @property
    def storage_service(self) -> SupabaseStorageService:
        if self._storage_service is None:
            self._storage_service = get_storage_service()
        return self._storage_service

    @property
    def document_processor(self) -> DocumentProcessor:
        if self._document_processor is None:
            self._document_processor = get_document_processor()
        return self._document_processor

    @property
    def medical_extraction_service(self) -> MedicalExtractionService:
        if self._medical_extraction_service is None:
            self._medical_extraction_service = get_medical_extraction_service()
        return self._medical_extraction_service

    @property
    def medical_persistence_service(self) -> MedicalPersistenceService:
        if self._medical_persistence_service is None:
            self._medical_persistence_service = get_medical_persistence_service()
        return self._medical_persistence_service

    def is_extraction_active(self, document_id: UUID) -> bool:
        """Checks if a document extraction job is currently active in background."""
        with _active_extractions_lock:
            return document_id in _active_extractions

    def register_active_extraction(self, document_id: UUID) -> bool:
        """
        Registers document extraction job. Returns True if successfully registered,
        or False if extraction is already active.
        """
        with _active_extractions_lock:
            if document_id in _active_extractions:
                return False
            _active_extractions.add(document_id)
            return True

    def unregister_active_extraction(self, document_id: UUID) -> None:
        """Unregisters document extraction job after completion or error."""
        with _active_extractions_lock:
            _active_extractions.discard(document_id)

    def process_user_document(
        self,
        user: User,
        document_id: UUID,
        db: Session,
    ) -> DocumentProcessResult:
        """
        Processes a document belonging to the authenticated user.
        """
        # 1. Resolve Patient Profile
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient:
            logger.warning("Patient profile not found for user %s", user.id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No patient profile found for the authenticated user.",
            )

        # 2. Retrieve Document Record
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        # 3. Enforce Strict Tenant & Ownership Isolation
        if document.patient_id != patient.id:
            logger.warning(
                "Unauthorized process attempt on document %s by user %s (patient %s)",
                document_id,
                user.id,
                patient.id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to process this document.",
            )

        # 4. Transition State to PROCESSING
        setattr(document, "processing_status", "PROCESSING")
        setattr(document, "error_message", None)
        db.commit()
        db.refresh(document)

        # 5. Download Private File from Supabase Storage
        file_bytes: bytes
        storage_path: str = str(document.file_path)
        t_dl_start = time.perf_counter()
        try:
            file_bytes = self.storage_service.download_file(storage_path)
            t_dl = time.perf_counter() - t_dl_start
            logger.info("[DOCUMENT] Download completed in %.2fs", t_dl)
        except StorageError as se:
            logger.error("Storage download failed for document %s: %s", document_id, type(se).__name__)
            setattr(document, "processing_status", "FAILED")
            setattr(document, "error_message", "Failed to download document from secure storage.")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to download document from secure storage.",
            )
        except Exception as e:
            logger.error("Unexpected storage error for document %s: %s", document_id, type(e).__name__)
            setattr(document, "processing_status", "FAILED")
            setattr(document, "error_message", "Storage error during document retrieval.")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving the document from storage.",
            )

        # 6. Execute Text Extraction via DocumentProcessor
        t_proc_start = time.perf_counter()
        try:
            proc_result: DocumentProcessingResult = self.document_processor.process_document(file_bytes)
            t_proc = time.perf_counter() - t_proc_start
            if proc_result.extraction_method == "tesseract":
                logger.info("[DOCUMENT] OCR completed in %.2fs", t_proc)
            else:
                logger.info("[DOCUMENT] PDF text extraction completed in %.2fs", t_proc)
        except InvalidPDFError as pe:
            logger.warning("Invalid or corrupt PDF for document %s: %s", document_id, type(pe).__name__)
            setattr(document, "processing_status", "FAILED")
            setattr(document, "error_message", "Invalid or unreadable PDF document.")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The provided document could not be read or parsed as a valid PDF.",
            )
        except (OCRError, DocumentProcessingError) as de:
            logger.error("Document processing error for %s: %s", document_id, type(de).__name__)
            setattr(document, "processing_status", "FAILED")
            setattr(document, "error_message", "Error occurred during text extraction processing.")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process document contents.",
            )
        except Exception as e:
            logger.error("Unexpected processing failure for document %s: %s", document_id, type(e).__name__)
            setattr(document, "processing_status", "FAILED")
            setattr(document, "error_message", "Unexpected failure during document processing.")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing the document.",
            )

        # 7. Update Document Record to COMPLETED and Persist Core Extraction Results
        now_utc = datetime.now()
        setattr(document, "processing_status", "COMPLETED")
        setattr(document, "processed_at", now_utc)
        setattr(document, "error_message", None)
        setattr(document, "extracted_text", proc_result.extracted_text)
        setattr(document, "extraction_method", proc_result.extraction_method)
        setattr(document, "page_count", proc_result.page_count)
        db.commit()
        db.refresh(document)

        doc_id = document.id if isinstance(document.id, UUID) else UUID(str(document.id))
        pat_id = document.patient_id if isinstance(document.patient_id, UUID) else UUID(str(document.patient_id))
        file_name = str(document.file_name)
        status_str = str(document.processing_status)
        proc_at = document.processed_at if isinstance(document.processed_at, datetime) else now_utc

        logger.info(
            "Document %s successfully processed (method=%s, pages=%d, has_text=%s)",
            doc_id,
            proc_result.extraction_method,
            proc_result.page_count,
            proc_result.has_text,
        )

        return DocumentProcessResult(
            document_id=doc_id,
            patient_id=pat_id,
            file_name=file_name,
            processing_status=status_str,
            extracted_text=proc_result.extracted_text,
            page_count=proc_result.page_count,
            extraction_method=proc_result.extraction_method,
            has_text=proc_result.has_text,
            confidence=proc_result.confidence,
            processed_at=proc_at,
        )

    def extract_user_document(
        self,
        user: User,
        document_id: UUID,
        db: Session,
    ) -> MedicalExtractionResponse:
        """
        Extracts structured clinical information from a processed document and persists into database.
        """
        t_start = time.perf_counter()

        # 1. Resolve Patient Profile
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient:
            logger.warning("Patient profile not found for user %s", user.id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No patient profile found for the authenticated user.",
            )

        # 2. Retrieve Document Record
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        # 3. Enforce Strict Tenant & Ownership Isolation
        if document.patient_id != patient.id:
            logger.warning(
                "Unauthorized extract attempt on document %s by user %s (patient %s)",
                document_id,
                user.id,
                patient.id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to process this document.",
            )

        # 4. If text has not been extracted yet, trigger text extraction pipeline
        if not document.extracted_text or document.processing_status != "COMPLETED":
            self.process_user_document(user=user, document_id=document_id, db=db)
            db.refresh(document)

        # 5. Extract structured medical entities via AI
        t_ai_start = time.perf_counter()
        try:
            extracted_record = self.medical_extraction_service.extract_from_text(cast(Optional[str], document.extracted_text))
            t_ai = time.perf_counter() - t_ai_start
            logger.info("[DOCUMENT] Gemini extraction completed in %.2fs", t_ai)
        except AIServiceError as ae:
            logger.error("AI extraction error for document %s: %s", document_id, str(ae))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI medical extraction failed: {str(ae)}",
            )
        except Exception as e:
            logger.error("Unexpected failure during AI extraction for %s: %s", document_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract medical information from document.",
            )

        # 6. Persist structured entities into SQLAlchemy models
        doc_uuid = document.id if isinstance(document.id, UUID) else UUID(str(document.id))
        pat_uuid = patient.id if isinstance(patient.id, UUID) else UUID(str(patient.id))

        t_pers_start = time.perf_counter()
        try:
            persisted_counts = self.medical_persistence_service.persist_extracted_record(
                db=db,
                patient_id=pat_uuid,
                document_id=doc_uuid,
                extracted=extracted_record,
            )
            t_pers = time.perf_counter() - t_pers_start
            logger.info("[DOCUMENT] Persistence completed in %.2fs", t_pers)
        except Exception as pe:
            logger.error("Failed to persist extraction results for document %s: %s", document_id, str(pe))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist extracted clinical information.",
            )

        t_total = time.perf_counter() - t_start
        logger.info("[DOCUMENT] Total processing time %.2fs", t_total)

        return MedicalExtractionResponse(
            document_id=doc_uuid,
            patient_id=pat_uuid,
            status="COMPLETED",
            extracted_record=extracted_record,
            persisted_counts=persisted_counts,
            extracted_at=datetime.now(),
        )

    def run_background_extraction(self, document_id: UUID, user_id: UUID, db: Optional[Session] = None) -> None:
        """
        Background task worker invoked via FastAPI BackgroundTasks.
        Executes text extraction, AI processing, and persistence asynchronously.
        Guarantees status transition to COMPLETED on success or FAILED on exception.
        """
        t_start = time.perf_counter()
        if not self.register_active_extraction(document_id):
            logger.warning("[DOCUMENT] Extraction requested for %s, but job is already active.", document_id)
            return

        should_close = False
        if db is not None:
            active_db = db
        elif self._db_session_factory is not None:
            active_db = self._db_session_factory()
            should_close = True
        else:
            from app.db.database import SessionLocal
            active_db = SessionLocal()
            should_close = True

        try:
            user = active_db.query(User).filter(User.id == user_id).first()
            document = active_db.query(Document).filter(Document.id == document_id).first()

            if not user or not document:
                logger.error("[DOCUMENT] Background task error: user %s or document %s not found", user_id, document_id)
                return

            setattr(document, "processing_status", "PROCESSING")
            setattr(document, "error_message", None)
            active_db.commit()

            # 1. Download file
            t_dl_start = time.perf_counter()
            file_bytes = self.storage_service.download_file(str(document.file_path))
            t_dl = time.perf_counter() - t_dl_start
            logger.info("[DOCUMENT] Download completed in %.2fs", t_dl)

            # 2. Text Extraction & OCR
            t_proc_start = time.perf_counter()
            proc_result = self.document_processor.process_document(file_bytes)
            t_proc = time.perf_counter() - t_proc_start
            if proc_result.extraction_method == "tesseract":
                logger.info("[DOCUMENT] OCR completed in %.2fs", t_proc)
            else:
                logger.info("[DOCUMENT] PDF text extraction completed in %.2fs", t_proc)

            now_utc = datetime.now()
            setattr(document, "extracted_text", proc_result.extracted_text)
            setattr(document, "extraction_method", proc_result.extraction_method)
            setattr(document, "page_count", proc_result.page_count)
            setattr(document, "processed_at", now_utc)
            active_db.commit()
            active_db.refresh(document)

            # 3. Gemini AI Extraction
            t_ai_start = time.perf_counter()
            extracted_record = self.medical_extraction_service.extract_from_text(cast(Optional[str], document.extracted_text))
            t_ai = time.perf_counter() - t_ai_start
            logger.info("[DOCUMENT] Gemini extraction completed in %.2fs", t_ai)

            # 4. Medical Persistence
            t_pers_start = time.perf_counter()
            doc_uuid = document.id if isinstance(document.id, UUID) else UUID(str(document.id))
            pat_uuid = document.patient_id if isinstance(document.patient_id, UUID) else UUID(str(document.patient_id))

            self.medical_persistence_service.persist_extracted_record(
                db=active_db,
                patient_id=pat_uuid,
                document_id=doc_uuid,
                extracted=extracted_record,
            )
            t_pers = time.perf_counter() - t_pers_start
            logger.info("[DOCUMENT] Persistence completed in %.2fs", t_pers)

            # Final Status Update
            setattr(document, "processing_status", "COMPLETED")
            setattr(document, "processed_at", datetime.now())
            setattr(document, "error_message", None)
            active_db.commit()

            t_total = time.perf_counter() - t_start
            logger.info("[DOCUMENT] Total processing time %.2fs for document %s", t_total, document_id)

        except Exception as exc:
            active_db.rollback()
            logger.error("[DOCUMENT] Background extraction failed for document %s: %s", document_id, str(exc), exc_info=True)
            try:
                doc_record = active_db.query(Document).filter(Document.id == document_id).first()
                if doc_record:
                    setattr(doc_record, "processing_status", "FAILED")
                    setattr(doc_record, "error_message", str(exc))
                    active_db.commit()
            except Exception as update_err:
                logger.error("[DOCUMENT] Failed to set FAILED status for document %s: %s", document_id, str(update_err))
        finally:
            if should_close:
                active_db.close()
            self.unregister_active_extraction(document_id)


_default_processing_service: Optional[DocumentProcessingService] = None


def get_document_processing_service() -> DocumentProcessingService:
    """
    Returns a shared singleton instance of DocumentProcessingService.
    """
    global _default_processing_service
    if _default_processing_service is None:
        _default_processing_service = DocumentProcessingService()
    return _default_processing_service
