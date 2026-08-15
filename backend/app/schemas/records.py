from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MedicationRecordResponse(BaseModel):
    """
    Public schema for patient medication and prescription details.
    """

    id: UUID = Field(..., description="Unique medication identifier")
    name: str = Field(..., description="Medication name")
    normalized_name: str = Field(..., description="Normalized generic ingredient name")
    dosage: Optional[str] = Field(default=None, description="Prescribed dosage strength")
    frequency: Optional[str] = Field(default=None, description="Dosing frequency")
    start_date: Optional[date] = Field(default=None, description="Start date")
    end_date: Optional[date] = Field(default=None, description="End date")
    instructions: Optional[str] = Field(default=None, description="Administration instructions")
    source_document_id: Optional[UUID] = Field(default=None, description="ID of source document")
    source_document_name: Optional[str] = Field(default=None, description="Filename of source document")
    status: str = Field(default="active", description="Medication status ('active' or 'stopped')")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class FindingRecordResponse(BaseModel):
    """
    Public schema for patient clinical findings and AI-detected risk items.
    """

    id: UUID = Field(..., description="Unique finding identifier")
    finding_type: str = Field(..., description="Finding category (e.g. diagnosis, risk_factor, allergy)")
    title: str = Field(..., description="Finding title")
    description: str = Field(..., description="Finding description")
    risk_level: Optional[str] = Field(default="low", description="Risk level (low, medium, high)")
    confidence: Optional[float] = Field(default=None, description="Confidence score")
    recommendation: Optional[str] = Field(default=None, description="Clinical recommendation")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class LabResultRecordResponse(BaseModel):
    """
    Public schema for patient laboratory and diagnostic test results.
    """

    id: UUID = Field(..., description="Unique lab result identifier")
    test_name: str = Field(..., description="Test or biomarker name")
    value: str = Field(..., description="Reported result value")
    unit: Optional[str] = Field(default=None, description="Measurement unit")
    reference_range: Optional[str] = Field(default=None, description="Reference range")
    result_date: Optional[date] = Field(default=None, description="Date of result")
    source_document_id: Optional[UUID] = Field(default=None, description="ID of source document")
    source_document_name: Optional[str] = Field(default=None, description="Filename of source document")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class MedicalEventRecordResponse(BaseModel):
    """
    Public schema for patient timeline medical events.
    """

    id: UUID = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Event kind (consultation, lab_test, diagnosis, procedure)")
    event_date: Optional[date] = Field(default=None, description="Date event occurred")
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(default=None, description="Event description")
    source_document_id: Optional[UUID] = Field(default=None, description="ID of source document")
    source_document_name: Optional[str] = Field(default=None, description="Filename of source document")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class AllergyRecordResponse(BaseModel):
    """
    Public schema for patient drug allergies.
    """

    id: UUID = Field(..., description="Unique allergy identifier")
    medication_name: str = Field(..., description="Allergen or drug name")
    normalized_medication_name: Optional[str] = Field(default=None, description="Normalized allergen name")
    reaction: Optional[str] = Field(default=None, description="Allergic reaction symptoms")
    severity: Optional[str] = Field(default=None, description="Severity (mild, moderate, severe)")
    source_document_id: Optional[UUID] = Field(default=None, description="ID of source document")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class AIAnalysisRecordResponse(BaseModel):
    """
    Public schema for AI analysis entries.
    """

    id: UUID = Field(..., description="Unique AI analysis identifier")
    analysis_type: str = Field(..., description="Analysis type (e.g. document_extraction, cross_check)")
    result: Dict[str, Any] = Field(default_factory=dict, description="Structured analysis result payload")
    confidence: Optional[float] = Field(default=None, description="Confidence score")
    created_at: datetime = Field(..., description="Timestamp of analysis")

    model_config = ConfigDict(from_attributes=True)


class MedicalOverviewResponse(BaseModel):
    """
    Consolidated medical overview for the authenticated patient dashboard.
    """

    patient_id: UUID = Field(..., description="Patient identifier")
    total_documents: int = Field(default=0, description="Total uploaded documents")
    total_medications: int = Field(default=0, description="Total active medications")
    total_findings: int = Field(default=0, description="Total AI findings")
    total_events: int = Field(default=0, description="Total medical timeline events")
    total_lab_results: int = Field(default=0, description="Total lab results")
    total_allergies: int = Field(default=0, description="Total recorded allergies")
    latest_summary: Optional[str] = Field(default=None, description="Executive clinical summary from latest AI analysis")
    confidence_score: Optional[float] = Field(default=None, description="Latest AI analysis confidence score")
    recent_events: List[MedicalEventRecordResponse] = Field(default_factory=list, description="Recent timeline events")
    active_medications: List[MedicationRecordResponse] = Field(default_factory=list, description="Active medications")
    priority_findings: List[FindingRecordResponse] = Field(default_factory=list, description="Priority findings")

    model_config = ConfigDict(from_attributes=True)
