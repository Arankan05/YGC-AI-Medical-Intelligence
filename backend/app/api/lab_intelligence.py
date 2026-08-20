import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.records import get_patient_for_user
from app.core.security import get_current_application_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.lab_intelligence import (
    LabIntelligenceCombinedResponse,
    LabIntelligenceOverviewResponse,
    LabIntelligenceTrendsResponse,
    LabResultAnalysisResponse,
    LabTrendPointResponse,
    LabTrendResponse,
)
from app.services.lab_intelligence_service import (
    LabResultAnalysis,
    LabTrend,
    LabTrendPoint,
    get_lab_intelligence_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lab-intelligence", tags=["lab_intelligence"])


def _map_result(analysis: LabResultAnalysis) -> LabResultAnalysisResponse:
    """
    Helper to convert a LabResultAnalysis into LabResultAnalysisResponse.

    The patient identifier is deliberately not exposed; the caller is already
    scoped to their own patient record by the endpoint.
    """
    return LabResultAnalysisResponse(
        id=analysis.id,
        test_name=analysis.test_name,
        value=analysis.value,
        numeric_value=analysis.numeric_value,
        unit=analysis.unit,
        reference_range=analysis.reference_range,
        result_date=analysis.result_date,
        status=analysis.status,
        source_document_id=analysis.source_document_id,
        source_document_name=analysis.source_document_name,
    )


def _map_trend_point(point: LabTrendPoint) -> LabTrendPointResponse:
    """
    Helper to convert a LabTrendPoint into LabTrendPointResponse.
    """
    return LabTrendPointResponse(
        result_date=point.result_date,
        value=point.value,
        numeric_value=point.numeric_value,
        unit=point.unit,
        status=point.status,
        source_document_id=point.source_document_id,
        source_document_name=point.source_document_name,
    )


def _map_trend(trend: LabTrend) -> LabTrendResponse:
    """
    Helper to convert a LabTrend into LabTrendResponse.
    """
    return LabTrendResponse(
        test_name=trend.test_name,
        unit=trend.unit,
        trend=trend.trend,
        points=[_map_trend_point(p) for p in trend.points],
    )


@router.get(
    "/combined",
    response_model=LabIntelligenceCombinedResponse,
    summary="Get combined laboratory overview and trends in a single database query",
    description="Returns analysed results, available test names, and historical trends for the authenticated patient in one network request.",
)
def get_combined_lab_intelligence(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> LabIntelligenceCombinedResponse:
    patient = get_patient_for_user(current_user, db)
    service = get_lab_intelligence_service()

    analyses, available_tests, trends = service.get_combined_intelligence(
        db=db, patient_id=patient.id
    )

    return LabIntelligenceCombinedResponse(
        results=[_map_result(a) for a in analyses],
        available_tests=list(available_tests),
        trends=[_map_trend(t) for t in trends],
    )


@router.get(
    "/overview",
    response_model=LabIntelligenceOverviewResponse,
    summary="Get the authenticated patient's analysed laboratory results",
    description="Classifies every laboratory result belonging to the authenticated patient against its reference range and returns the results together with the distinct test names available for that patient. Nothing is written to the database.",
)
def get_lab_intelligence_overview(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> LabIntelligenceOverviewResponse:
    patient = get_patient_for_user(current_user, db)
    service = get_lab_intelligence_service()

    analyses = service.analyze_patient_labs(db=db, patient_id=patient.id)
    available_tests = service.get_available_tests(db=db, patient_id=patient.id)

    return LabIntelligenceOverviewResponse(
        results=[_map_result(a) for a in analyses],
        available_tests=list(available_tests),
    )


@router.get(
    "/trends",
    response_model=LabIntelligenceTrendsResponse,
    summary="Get historical trends for every laboratory test the patient has",
    description="Returns the historical trend of each distinct laboratory test recorded for the authenticated patient, ordered alphabetically by test name. Tests with fewer than two numeric results are reported as INSUFFICIENT_DATA rather than omitted.",
)
def get_lab_intelligence_trends(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> LabIntelligenceTrendsResponse:
    patient = get_patient_for_user(current_user, db)
    trends = get_lab_intelligence_service().get_all_test_trends(
        db=db,
        patient_id=patient.id,
    )
    return LabIntelligenceTrendsResponse(
        trends=[_map_trend(t) for t in trends],
    )


@router.get(
    "/trends/{test_name}",
    response_model=LabTrendResponse,
    summary="Get the historical trend for one laboratory test",
    description="Returns the historical trend for a single laboratory test belonging to the authenticated patient. Matching is case-insensitive and ignores surrounding whitespace. Responds with HTTP 404 when the authenticated patient has no result under that name.",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The authenticated patient has no result for this test",
        },
    },
)
def get_lab_intelligence_test_trend(
    test_name: str,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> LabTrendResponse:
    patient = get_patient_for_user(current_user, db)
    trend = get_lab_intelligence_service().get_test_trend(
        db=db,
        patient_id=patient.id,
        test_name=test_name,
    )

    # The service query is already filtered by patient_id, so an empty result
    # means this patient has no such test. Another patient holding a result
    # under the same name cannot satisfy this lookup.
    if not trend.points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No laboratory results found for the requested test.",
        )

    return _map_trend(trend)
