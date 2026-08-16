from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SafetyIssueResponse(BaseModel):
    """
    Public schema for a single medication safety issue.
    """

    id: str = Field(..., description="Stable identifier for this issue (e.g. 'drug_interaction:aspirin+warfarin')")
    kind: str = Field(..., description="Flag category ('duplicate', 'allergy' or 'interaction')")
    finding_type: str = Field(..., description="Backend finding category stored on the Finding record")
    risk_level: str = Field(..., description="Risk level (low, medium, high)")
    title: str = Field(..., description="Short headline for the issue")
    medications: List[str] = Field(default_factory=list, description="Names of the medications involved")
    description: str = Field(..., description="Human-readable explanation of the issue")
    recommendation: Optional[str] = Field(default=None, description="Suggested action for the patient")
    confidence: Optional[float] = Field(default=None, description="Confidence score between 0.0 and 1.0")

    model_config = ConfigDict(from_attributes=True)


class MedicationSafetyReportResponse(BaseModel):
    """
    Public schema for a patient's medication safety report.
    """

    reference_date: date = Field(..., description="Date used to decide whether a prescription is active")
    active_medication_count: int = Field(default=0, description="Number of distinct active medications analysed")
    active_medications: List[str] = Field(default_factory=list, description="Normalized names of the active medications analysed")
    finding_count: int = Field(default=0, description="Total number of safety issues detected")
    highest_risk_level: Optional[str] = Field(default=None, description="Highest risk level present, or null when there are no issues")
    issues: List[SafetyIssueResponse] = Field(default_factory=list, description="Detected safety issues, most severe first")

    model_config = ConfigDict(from_attributes=True)


class MedicationSafetyPersistenceCountsResponse(BaseModel):
    """
    Public schema for the row counts produced when safety findings are stored.
    """

    created: int = Field(default=0, description="Newly recorded safety findings")
    updated: int = Field(default=0, description="Existing safety findings refreshed with new content")
    unchanged: int = Field(default=0, description="Safety findings that were already up to date")
    removed: int = Field(default=0, description="Safety findings deleted because they no longer apply")

    model_config = ConfigDict(from_attributes=True)


class MedicationSafetyAnalysisResponse(BaseModel):
    """
    Public schema returned after analysing and persisting medication safety findings.
    """

    report: MedicationSafetyReportResponse = Field(..., description="Safety report produced by the analysis")
    persistence: MedicationSafetyPersistenceCountsResponse = Field(..., description="Counts of the Finding records written")

    model_config = ConfigDict(from_attributes=True)
