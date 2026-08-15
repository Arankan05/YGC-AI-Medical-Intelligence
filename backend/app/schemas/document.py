import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


from app.schemas.records import (
    AllergyRecordResponse,
    FindingRecordResponse,
    LabResultRecordResponse,
    MedicalEventRecordResponse,
    MedicationRecordResponse,
)


class DocumentResponse(BaseModel):
    """
    Public response schema for medical document metadata.
    Excludes sensitive storage keys, internal tokens, and raw database internals.
    """

    id: UUID = Field(..., description="Unique document identifier")
    patient_id: UUID = Field(..., description="Patient identifier associated with this document")
    file_name: str = Field(..., description="Sanitized display name of the uploaded file")
    file_path: str = Field(..., description="Ownership-scoped storage path in private bucket")
    document_type: str = Field(..., description="Document type category (e.g. lab_report, prescription, unknown)")
    processing_status: str = Field(..., description="Current processing lifecycle status (e.g. UPLOADED)")
    uploaded_at: datetime = Field(..., description="Timestamp when the document was uploaded")
    processed_at: Optional[datetime] = Field(default=None, description="Timestamp when processing completed, if applicable")
    error_message: Optional[str] = Field(default=None, description="Error message if document processing encountered issues")
    extraction_method: Optional[str] = Field(default=None, description="Extraction method used ('pymupdf' or 'tesseract')")
    page_count: Optional[int] = Field(default=None, description="Total pages processed")
    extracted_text: Optional[str] = Field(default=None, description="Extracted clinical text if available")

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    """
    Comprehensive document detail schema including all extracted clinical entities.
    """

    medications: List[MedicationRecordResponse] = Field(default_factory=list, description="Prescriptions extracted from this document")
    findings: List[FindingRecordResponse] = Field(default_factory=list, description="Clinical findings associated with patient")
    lab_results: List[LabResultRecordResponse] = Field(default_factory=list, description="Lab test results extracted from this document")
    allergies: List[AllergyRecordResponse] = Field(default_factory=list, description="Drug allergies extracted from this document")
    events: List[MedicalEventRecordResponse] = Field(default_factory=list, description="Medical timeline events extracted from this document")
    ai_summary: Optional[str] = Field(default=None, description="AI-extracted summary for this document / patient")
    ai_confidence: Optional[float] = Field(default=None, description="AI extraction confidence score")

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """
    Response schema for listing documents belonging to the authenticated user's patient.
    """

    items: List[DocumentResponse] = Field(default_factory=list, description="List of document metadata records")
    total: int = Field(..., description="Total number of documents returned")

    model_config = ConfigDict(from_attributes=True)


class DocumentDeleteResponse(BaseModel):
    """
    Response schema confirming successful document deletion.
    """

    message: str = Field(default="Document deleted successfully", description="Deletion confirmation message")
    id: UUID = Field(..., description="Identifier of the deleted document")

    model_config = ConfigDict(from_attributes=True)


class DocumentProcessResponse(BaseModel):
    """
    Public response schema for processed document extraction results.
    """

    document_id: UUID = Field(..., description="Unique document identifier")
    patient_id: UUID = Field(..., description="Patient identifier associated with this document")
    file_name: str = Field(..., description="Original display filename of the document")
    processing_status: str = Field(..., description="Final processing lifecycle status (e.g. COMPLETED, FAILED)")
    extracted_text: str = Field(..., description="Full extracted clinical text from document with page boundaries")
    page_count: int = Field(..., description="Total pages processed")
    extraction_method: str = Field(..., description="Extraction strategy used ('pymupdf' or 'tesseract')")
    has_text: bool = Field(..., description="Whether extractable text was found in the document")
    confidence: Optional[float] = Field(default=None, description="Average OCR confidence score if OCR was used")
    processed_at: Optional[datetime] = Field(default=None, description="Timestamp when processing completed")

    model_config = ConfigDict(from_attributes=True)

