import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

_KNOWN_NON_DATE_STRINGS = {
    "",
    "none",
    "null",
    "unknown",
    "n/a",
    "na",
    "undefined",
    "nil",
    "unspecified",
    "not specified",
    "missing",
    "not available",
    "invalid",
    "x",
    "xx",
    "xxx",
    "xxxx",
}

_ACCEPTED_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)


def sanitize_extracted_date(v: Any) -> Optional[date]:
    """
    Defensively normalizes and validates AI-extracted clinical date fields.

    Medical Safety Rules:
    - Never guess, invent, or extrapolate missing date components.
    - Full valid dates (e.g., '2026-08-15') are parsed into standard datetime.date objects.
    - Ambiguous, placeholder (e.g., '200X-07-07', '20XX-??-??'), incomplete (e.g. '2024', '2024-07'),
      empty (''), or text-marker ('unknown', 'null', 'N/A') dates are safely converted to None.
    """
    if v is None:
        return None

    if isinstance(v, datetime):
        return v.date()

    if isinstance(v, date):
        return v

    if not isinstance(v, str):
        return None

    raw_str = v.strip()
    if not raw_str:
        return None

    if raw_str.lower() in _KNOWN_NON_DATE_STRINGS:
        return None

    # Check for placeholder wildcards, partial year masks, or template strings
    if any(ch in raw_str for ch in ("x", "X", "?", "*", "_")) or "yyyy" in raw_str.lower():
        return None

    # Try ISO-8601 parsing first
    try:
        parsed_iso = date.fromisoformat(raw_str)
        if 1900 <= parsed_iso.year <= 2100:
            return parsed_iso
    except (ValueError, TypeError):
        pass

    # Try standard explicit complete date formats
    for fmt in _ACCEPTED_DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw_str, fmt).date()
            if 1900 <= parsed.year <= 2100:
                return parsed
        except (ValueError, TypeError):
            continue

    # Unrecognized, partial, or malformed date string -> return None (never guess)
    return None


class ExtractedMedicalEvent(BaseModel):
    """
    Extracted medical event entity (e.g. consultation, admission, procedure, diagnosis).
    """

    event_type: str = Field(
        default="consultation",
        description="Type of medical event (e.g., consultation, lab_test, diagnosis, procedure, admission, discharge, prescription)",
    )
    event_date: Optional[date] = Field(
        default=None,
        description="Date when the event occurred (YYYY-MM-DD)",
    )
    title: str = Field(
        ...,
        description="Brief title or name of the medical event",
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description or clinical notes regarding the event",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("event_date", mode="before")
    @classmethod
    def validate_event_date(cls, v: Any) -> Optional[date]:
        return sanitize_extracted_date(v)


class ExtractedMedication(BaseModel):
    """
    Extracted medication and associated prescription details.
    """

    name: str = Field(
        ...,
        description="Brand or generic medication name (e.g., 'Amoxicillin 500mg')",
    )
    normalized_name: Optional[str] = Field(
        default=None,
        description="Normalized lowercase generic name (e.g., 'amoxicillin')",
    )
    dosage: Optional[str] = Field(
        default=None,
        description="Prescribed dosage strength (e.g., '500mg', '10ml')",
    )
    frequency: Optional[str] = Field(
        default=None,
        description="Frequency of administration (e.g., 'twice daily', 'every 8 hours')",
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Start date of the medication regimen (YYYY-MM-DD)",
    )
    end_date: Optional[date] = Field(
        default=None,
        description="End date of the medication regimen (YYYY-MM-DD)",
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Patient administration instructions or cautionary advice",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_medication_dates(cls, v: Any) -> Optional[date]:
        return sanitize_extracted_date(v)

    @model_validator(mode="after")
    def populate_normalized_name(self) -> "ExtractedMedication":
        if not self.normalized_name and self.name:
            self.normalized_name = self.name.strip().lower()
        elif self.normalized_name:
            self.normalized_name = self.normalized_name.strip().lower()
        return self


class ExtractedLabResult(BaseModel):
    """
    Extracted laboratory or diagnostic test result.
    """

    test_name: str = Field(
        ...,
        description="Name of the laboratory test (e.g., 'HbA1c', 'WBC', 'Total Cholesterol')",
    )
    value: str = Field(
        ...,
        description="Measured result value as reported (e.g., '5.7', '140', 'Negative')",
    )
    unit: Optional[str] = Field(
        default=None,
        description="Measurement unit (e.g., 'mg/dL', '%', 'mmol/L')",
    )
    reference_range: Optional[str] = Field(
        default=None,
        description="Standard reference range (e.g., '70-99 mg/dL', '< 5.7%')",
    )
    result_date: Optional[date] = Field(
        default=None,
        description="Date the test was performed or reported (YYYY-MM-DD)",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("result_date", mode="before")
    @classmethod
    def validate_result_date(cls, v: Any) -> Optional[date]:
        return sanitize_extracted_date(v)


class ExtractedAllergy(BaseModel):
    """
    Extracted patient medication allergy or adverse reaction.
    """

    medication_name: str = Field(
        ...,
        description="Medication or substance causing the allergic reaction (e.g., 'Penicillin')",
    )
    normalized_medication_name: Optional[str] = Field(
        default=None,
        description="Normalized lowercase allergen name (e.g., 'penicillin')",
    )
    reaction: Optional[str] = Field(
        default=None,
        description="Manifestation or symptoms of reaction (e.g., 'Hives', 'Anaphylaxis')",
    )
    severity: Optional[str] = Field(
        default=None,
        description="Severity level (e.g., 'mild', 'moderate', 'severe', 'life-threatening')",
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def populate_normalized_allergen(self) -> "ExtractedAllergy":
        if not self.normalized_medication_name and self.medication_name:
            self.normalized_medication_name = self.medication_name.strip().lower()
        elif self.normalized_medication_name:
            self.normalized_medication_name = self.normalized_medication_name.strip().lower()
        return self


class ExtractedFinding(BaseModel):
    """
    Extracted clinical finding, diagnosis, or key risk indicator.
    """

    finding_type: str = Field(
        default="diagnosis",
        description="Category of finding (e.g., 'diagnosis', 'symptom', 'vital_sign', 'risk_factor', 'clinical_note')",
    )
    title: str = Field(
        ...,
        description="Short title or diagnosis name (e.g., 'Type 2 Diabetes Mellitus')",
    )
    description: str = Field(
        ...,
        description="Detailed description or context of the clinical finding",
    )
    risk_level: Optional[str] = Field(
        default="low",
        description="Assessed risk level ('low', 'medium', 'high', 'critical')",
    )
    confidence: Optional[float] = Field(
        default=0.9,
        description="Confidence score for this finding (0.0 to 1.0)",
    )
    recommendation: Optional[str] = Field(
        default=None,
        description="Clinical recommendation, next steps, or specialty follow-up",
    )

    model_config = ConfigDict(from_attributes=True)


class ExtractedMedicalRecord(BaseModel):
    """
    Aggregate structured record containing all clinical data extracted from a document.
    """

    document_type_detected: Optional[str] = Field(
        default="unknown",
        description="Detected medical document category (e.g., 'prescription', 'lab_report', 'discharge_summary', 'consultation_note')",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Concise executive clinical summary of the document",
    )
    confidence_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Overall confidence score for the extraction (0.0 to 1.0)",
    )
    events: List[ExtractedMedicalEvent] = Field(
        default_factory=list,
        description="List of extracted medical events and consultations",
    )
    medications: List[ExtractedMedication] = Field(
        default_factory=list,
        description="List of extracted medications and prescriptions",
    )
    lab_results: List[ExtractedLabResult] = Field(
        default_factory=list,
        description="List of extracted diagnostic and laboratory results",
    )
    allergies: List[ExtractedAllergy] = Field(
        default_factory=list,
        description="List of documented allergies and adverse drug reactions",
    )
    findings: List[ExtractedFinding] = Field(
        default_factory=list,
        description="List of extracted clinical findings, diagnoses, and risk factors",
    )

    model_config = ConfigDict(from_attributes=True)


class MedicalExtractionResponse(BaseModel):
    """
    Public response schema returned by the extraction endpoint.
    """

    document_id: UUID = Field(..., description="UUID of the source document")
    patient_id: UUID = Field(..., description="UUID of the owning patient")
    status: str = Field(default="COMPLETED", description="Extraction status ('COMPLETED' or 'FAILED')")
    extracted_record: ExtractedMedicalRecord = Field(..., description="Full structured clinical extraction record")
    persisted_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of database records created/updated per entity type",
    )
    extracted_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when extraction completed",
    )

    model_config = ConfigDict(from_attributes=True)
