from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LabResultAnalysisResponse(BaseModel):
    """Analyzed laboratory result."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    test_name: str
    value: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    result_date: Optional[date] = None
    status: str
    # Nullable: a lab result may be recorded without a source document, and the
    # document FK is ON DELETE SET NULL. Only the display name is exposed;
    # file_path is internal storage detail.
    source_document_id: Optional[UUID] = None
    source_document_name: Optional[str] = None


class LabTrendPointResponse(BaseModel):
    """Historical laboratory result point."""

    result_date: Optional[date] = None
    value: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    status: str
    source_document_id: Optional[UUID] = None
    source_document_name: Optional[str] = None


class LabTrendResponse(BaseModel):
    """Historical trend for one laboratory test."""

    test_name: str
    unit: Optional[str] = None
    trend: str
    points: list[LabTrendPointResponse]


class LabIntelligenceOverviewResponse(BaseModel):
    """Complete laboratory intelligence overview."""

    results: list[LabResultAnalysisResponse]
    available_tests: list[str]


class LabIntelligenceTrendsResponse(BaseModel):
    """Collection of laboratory trends."""

    trends: list[LabTrendResponse]


class LabIntelligenceCombinedResponse(BaseModel):
    """Combined laboratory overview and trends response."""

    results: list[LabResultAnalysisResponse]
    available_tests: list[str]
    trends: list[LabTrendResponse]