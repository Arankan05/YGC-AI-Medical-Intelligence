import logging
import re
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.security import get_current_application_user
from app.db.database import get_db
from app.models.ai_analysis import AIAnalysis
from app.models.allergy import Allergy
from app.models.document import Document
from app.models.finding import Finding
from app.models.lab_result import LabResult
from app.models.medical_event import MedicalEvent
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentProcessResponse,
    DocumentResponse,
)
from app.schemas.extraction import MedicalExtractionResponse
from app.schemas.records import (
    AllergyRecordResponse,
    FindingRecordResponse,
    LabResultRecordResponse,
    MedicalEventRecordResponse,
    MedicationRecordResponse,
)
from app.services.document_processing_service import (
    DocumentProcessingService,
    get_document_processing_service,
)
from app.services.storage_service import (
    StorageError,
    SupabaseStorageService,
    get_storage_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

ALLOWED_MIME_TYPES = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
}

ALLOWED_DOCUMENT_TYPES = {
    "prescription",
    "lab_report",
    "medical_report",
    "scanned_document",
    "unknown",
}


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitizes raw uploaded filename to prevent directory traversal and harmful characters.
    Extracts only the basename, removes path traversal characters (../, ..\\),
    replaces whitespace with underscores, and retains only safe characters.
    """
    if not filename or not filename.strip():
        return "document.pdf"

    # Extract only the base name (strips path components)
    raw_name = Path(filename.strip()).name
    # Replace spaces with underscores
    clean_name = re.sub(r"\s+", "_", raw_name)
    # Retain only safe alphanumeric characters, dots, underscores, and hyphens
    clean_name = re.sub(r"[^a-zA-Z0-9._-]", "", clean_name)
    # Strip dangerous leading/trailing dots or underscores
    clean_name = clean_name.strip("._")

    if not clean_name:
        return "document.pdf"

    return clean_name


def sanitize_document_type(doc_type: Optional[str]) -> str:
    """
    Validates and normalizes document type against the allowed safe categories.
    Defaults to 'unknown' if not matched.
    """
    if not doc_type:
        return "unknown"
    cleaned = doc_type.strip().lower()
    if cleaned in ALLOWED_DOCUMENT_TYPES:
        return cleaned
    return "unknown"


def validate_file_content(contents: bytes, filename: str) -> str:
    """
    Validates file size, inspects file header magic bytes, and checks extension.
    Returns the verified MIME type.

    Raises:
        HTTPException(400): If file is empty, oversized, unsupported, or mismatched.
    """
    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size ({len(contents)} bytes) exceeds the maximum allowed limit of 25 MB.",
        )

    # Magic byte verification
    detected_mime: Optional[str] = None
    if contents.startswith(b"%PDF"):
        detected_mime = "application/pdf"
    elif contents.startswith(b"\xff\xd8\xff"):
        detected_mime = "image/jpeg"
    elif contents.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = "image/png"

    if not detected_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported or invalid file content. Allowed types: PDF (application/pdf), JPEG (image/jpeg), PNG (image/png).",
        )

    # Extension verification
    ext = Path(filename).suffix.lower()
    allowed_exts = ALLOWED_MIME_TYPES.get(detected_mime, [])
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' does not match detected MIME format '{detected_mime}'. Expected: {allowed_exts}",
        )

    return detected_mime


def get_patient_for_user(user: User, db: Session) -> Patient:
    """
    Resolves the Patient record associated with the authenticated User.

    Raises:
        HTTPException(404): If no patient record exists for the user.
    """
    patient = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not patient:
        logger.warning("No patient record found for user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patient profile found for the authenticated user. Please create a patient profile first.",
        )
    return patient


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a medical document",
    description="Uploads a medical document (PDF, JPEG, PNG <= 25MB) to secure storage, associates it with the authenticated user's patient, and creates a database record.",
)
async def upload_document(
    file: UploadFile = File(..., description="Medical document file (PDF, JPEG, PNG <= 25MB)"),
    document_type: Optional[str] = Form(default="unknown", description="Optional document type category"),
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    storage_service: SupabaseStorageService = Depends(get_storage_service),
) -> DocumentResponse:
    """
    Upload endpoint executing strict multi-stage validation and consistency guarantees:
    1. Authenticate user & resolve patient ownership.
    2. Read & validate file contents, size (max 25MB), magic bytes, and extension.
    3. Construct ownership-scoped storage path: {user_id}/{patient_id}/{document_id}/{safe_filename}.
    4. Upload to private Supabase Storage bucket.
    5. Create Document record in PostgreSQL with processing_status='UPLOADED'.
    6. Roll back storage file if database record insertion fails.
    """
    # 1. Resolve patient ownership
    patient = get_patient_for_user(current_user, db)

    # 2. Read and validate file content
    contents = await file.read()
    raw_filename = file.filename or "document.pdf"
    mime_type = validate_file_content(contents, raw_filename)

    # 3. Sanitize filename and document type
    safe_filename = sanitize_filename(raw_filename)
    safe_doc_type = sanitize_document_type(document_type)

    # 4. Generate unique document UUID and storage path
    document_id = uuid.uuid4()
    storage_path = f"{current_user.id}/{patient.id}/{document_id}/{safe_filename}"

    # 5. Upload to private storage
    try:
        storage_service.upload_file(
            file_bytes=contents,
            storage_path=storage_path,
            content_type=mime_type,
            upsert=False,
        )
    except StorageError as se:
        logger.error("Storage upload failed for document %s: %s", document_id, type(se).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document to secure storage.",
        )
    except Exception as e:
        logger.error("Unexpected error during document upload for %s: %s", document_id, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while uploading the document.",
        )

    # 6. Create database record with rollback consistency
    doc_record = Document(
        id=document_id,
        patient_id=patient.id,
        file_name=safe_filename,
        file_path=storage_path,
        document_type=safe_doc_type,
        processing_status="UPLOADED",
    )

    try:
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)
    except Exception as db_err:
        db.rollback()
        logger.error(
            "Database commit failed for document %s: %s. Cleaning up storage object at '%s'.",
            document_id,
            type(db_err).__name__,
            storage_path,
        )
        try:
            storage_service.delete_file(storage_path)
        except Exception as cleanup_err:
            logger.critical(
                "Failed to clean up storage object '%s' after DB commit failure: %s",
                storage_path,
                type(cleanup_err).__name__,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document record.",
        )

    return DocumentResponse.model_validate(doc_record)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List medical documents for current user's patient",
    description="Returns all medical documents belonging to the authenticated user's patient profile, ordered newest first.",
)
def list_documents(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """
    Lists all documents owned by the authenticated user's patient.
    Enforces strict tenant isolation: users can only list documents for their own patient.
    """
    patient = get_patient_for_user(current_user, db)

    documents = (
        db.query(Document)
        .filter(Document.patient_id == patient.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    items = [DocumentResponse.model_validate(doc) for doc in documents]
    return DocumentListResponse(items=items, total=len(items))


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get medical document metadata and extracted intelligence",
    description="Retrieves metadata and all associated extracted clinical entities for a specific document.",
)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    """
    Retrieves document metadata and all associated extracted entities for a single document.
    Validates ownership chain: User -> Patient -> Document.
    """
    patient = get_patient_for_user(current_user, db)

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.patient_id != patient.id:
        logger.warning(
            "Unauthorized access attempt to document %s by patient %s (user %s)",
            document_id,
            patient.id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this document.",
        )

    # 1. Associated Prescriptions / Medications
    prescriptions = (
        db.query(Prescription)
        .filter(Prescription.document_id == document_id)
        .all()
    )
    med_records = [
        MedicationRecordResponse(
            id=p.id,
            medication_id=p.medication_id,
            name=p.medication.name if p.medication else "Unknown Medication",
            normalized_name=p.medication.normalized_name if p.medication else None,
            dosage=p.dosage,
            frequency=p.frequency,
            start_date=p.start_date,
            end_date=p.end_date,
            instructions=p.instructions,
            source_document_id=document.id,
            source_document_name=document.file_name,
            created_at=p.created_at,
        )
        for p in prescriptions
    ]

    # 2. Associated Lab Results
    labs = db.query(LabResult).filter(LabResult.document_id == document_id).all()
    lab_records = [
        LabResultRecordResponse(
            id=l.id,
            test_name=l.test_name,
            value=l.value,
            unit=l.unit,
            reference_range=l.reference_range,
            result_date=l.result_date,
            source_document_id=document.id,
            source_document_name=document.file_name,
            created_at=l.created_at,
        )
        for l in labs
    ]

    # 3. Associated Allergies
    allergies = db.query(Allergy).filter(Allergy.source_document_id == document_id).all()
    allergy_records = [
        AllergyRecordResponse(
            id=a.id,
            medication_name=a.medication_name,
            normalized_medication_name=a.normalized_medication_name,
            reaction=a.reaction,
            severity=a.severity,
            source_document_id=document.id,
            created_at=a.created_at,
        )
        for a in allergies
    ]

    # 4. Associated Medical Events
    events = (
        db.query(MedicalEvent)
        .filter(MedicalEvent.document_id == document_id)
        .order_by(MedicalEvent.event_date.desc())
        .all()
    )
    event_records = [
        MedicalEventRecordResponse(
            id=e.id,
            event_type=e.event_type,
            event_date=e.event_date,
            title=e.title,
            description=e.description,
            source_document_id=document.id,
            source_document_name=document.file_name,
            created_at=e.created_at,
        )
        for e in events
    ]

    # 5. Patient Findings
    findings = (
        db.query(Finding)
        .filter(Finding.patient_id == patient.id)
        .order_by(Finding.created_at.desc())
        .all()
    )
    finding_records = [
        FindingRecordResponse(
            id=f.id,
            finding_type=f.finding_type,
            title=f.title,
            description=f.description,
            risk_level=f.risk_level,
            confidence=f.confidence,
            recommendation=f.recommendation,
            created_at=f.created_at,
        )
        for f in findings
    ]

    # 6. Latest AI analysis summary
    latest_analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.patient_id == patient.id)
        .order_by(AIAnalysis.created_at.desc())
        .first()
    )
    ai_summary = None
    ai_confidence = None
    if latest_analysis and isinstance(latest_analysis.result, dict):
        ai_summary = latest_analysis.result.get("summary")
        ai_confidence = latest_analysis.confidence

    return DocumentDetailResponse(
        id=document.id,
        patient_id=document.patient_id,
        file_name=document.file_name,
        file_path=document.file_path,
        document_type=document.document_type,
        processing_status=document.processing_status,
        uploaded_at=document.uploaded_at,
        processed_at=document.processed_at,
        error_message=document.error_message,
        extraction_method=document.extraction_method,
        page_count=document.page_count,
        extracted_text=document.extracted_text,
        medications=med_records,
        findings=finding_records,
        lab_results=lab_records,
        allergies=allergy_records,
        events=event_records,
        ai_summary=ai_summary,
        ai_confidence=ai_confidence,
    )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a medical document",
    description="Deletes a medical document from Supabase Storage and deletes the database record after verifying ownership.",
)
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    storage_service: SupabaseStorageService = Depends(get_storage_service),
) -> DocumentDeleteResponse:
    """
    Deletes a document from storage and database.
    Order of operations:
    1. Verify patient ownership (404/403).
    2. Delete the file from Supabase Storage.
    3. Delete the database record.
    If storage deletion fails, database deletion is aborted to prevent inconsistent state.
    """
    patient = get_patient_for_user(current_user, db)

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.patient_id != patient.id:
        logger.warning(
            "Unauthorized delete attempt for document %s by patient %s (user %s)",
            document_id,
            patient.id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this document.",
        )

    # 1. Delete from Supabase storage first
    file_path = str(document.file_path)
    try:
        storage_service.delete_file(file_path)
    except Exception as se:
        logger.error(
            "Failed to delete storage file '%s' for document %s: %s",
            file_path,
            document_id,
            type(se).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document from storage.",
        )

    # 2. Delete database record
    try:
        db.delete(document)
        db.commit()
    except Exception as db_err:
        db.rollback()
        logger.error(
            "Database deletion failed for document %s: %s",
            document_id,
            type(db_err).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document record from database.",
        )

    return DocumentDeleteResponse(
        message="Document deleted successfully",
        id=document_id,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Process an uploaded medical document",
    description="Extracts clinical text from an uploaded document using PyMuPDF or Tesseract OCR fallback and updates processing status.",
)
def process_document_endpoint(
    document_id: UUID,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    processing_service: DocumentProcessingService = Depends(get_document_processing_service),
) -> DocumentProcessResponse:
    """
    Protected document processing endpoint:
    1. Validates user authentication and patient profile.
    2. Enforces ownership isolation (User -> Patient -> Document).
    3. Downloads private document from storage.
    4. Extracts text via DocumentProcessor (PyMuPDF with OCR fallback).
    5. Updates processing status (PROCESSING -> COMPLETED or FAILED) and timestamps.
    6. Returns structured extraction result.
    """
    result = processing_service.process_user_document(
        user=current_user,
        document_id=document_id,
        db=db,
    )

    return DocumentProcessResponse(
        document_id=result.document_id,
        patient_id=result.patient_id,
        file_name=result.file_name,
        processing_status=result.processing_status,
        extracted_text=result.extracted_text,
        page_count=result.page_count,
        extraction_method=result.extraction_method,
        has_text=result.has_text,
        confidence=result.confidence,
        processed_at=result.processed_at,
    )


@router.post(
    "/{document_id}/extract",
    response_model=MedicalExtractionResponse,
    summary="Extract structured medical intelligence from document",
    description="Extracts structured clinical data (events, medications, prescriptions, lab results, allergies, findings) from document text using AI and persists into patient record.",
)
def extract_document_endpoint(
    document_id: UUID,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    processing_service: DocumentProcessingService = Depends(get_document_processing_service),
) -> MedicalExtractionResponse:
    """
    Protected document medical extraction endpoint:
    1. Validates user authentication and patient profile.
    2. Enforces ownership isolation (User -> Patient -> Document).
    3. Triggers text extraction if not previously completed.
    4. Extracts structured clinical information using configured AI provider (Google Gemini).
    5. Persists entities (MedicalEvent, Medication, Prescription, LabResult, Allergy, Finding, AIAnalysis).
    6. Returns structured extraction payload and persisted record counts.
    """
    return processing_service.extract_user_document(
        user=current_user,
        document_id=document_id,
        db=db,
    )

