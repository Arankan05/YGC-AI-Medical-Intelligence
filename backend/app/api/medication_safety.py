import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.records import get_patient_for_user
from app.core.security import get_current_application_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.medication_safety import (
    MedicationSafetyAnalysisResponse,
    MedicationSafetyPersistenceCountsResponse,
    MedicationSafetyReportResponse,
    SafetyIssueResponse,
)
from app.services.medication_safety_persistence_service import (
    MedicationSafetyPersistenceResult,
    get_medication_safety_persistence_service,
)
from app.services.medication_safety_service import (
    MedicationSafetyFinding,
    MedicationSafetyReport,
    get_medication_safety_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medication-safety", tags=["medication_safety"])


def _map_safety_issue(finding: MedicationSafetyFinding) -> SafetyIssueResponse:
    """
    Helper to convert a MedicationSafetyFinding into SafetyIssueResponse.
    """
    return SafetyIssueResponse(
        id=finding.issue_key,
        kind=finding.kind,
        finding_type=finding.finding_type,
        risk_level=finding.risk_level,
        title=finding.title,
        medications=list(finding.medications),
        description=finding.description,
        recommendation=finding.recommendation,
        confidence=finding.confidence,
    )


def _map_safety_report(report: MedicationSafetyReport) -> MedicationSafetyReportResponse:
    """
    Helper to convert a MedicationSafetyReport into MedicationSafetyReportResponse.

    The patient identifier carried by the report is deliberately not exposed.
    """
    return MedicationSafetyReportResponse(
        reference_date=report.reference_date,
        active_medication_count=report.active_medication_count,
        active_medications=list(report.active_medications),
        finding_count=report.finding_count,
        highest_risk_level=report.highest_risk_level,
        issues=[_map_safety_issue(f) for f in report.findings],
    )


def _map_analysis_response(
    result: MedicationSafetyPersistenceResult,
) -> MedicationSafetyAnalysisResponse:
    """
    Helper to convert a MedicationSafetyPersistenceResult into MedicationSafetyAnalysisResponse.
    """
    return MedicationSafetyAnalysisResponse(
        report=_map_safety_report(result.report),
        persistence=MedicationSafetyPersistenceCountsResponse(
            created=result.created,
            updated=result.updated,
            unchanged=result.unchanged,
            removed=result.removed,
        ),
    )


@router.get(
    "/check",
    response_model=MedicationSafetyReportResponse,
    summary="Check the authenticated patient's medications for safety issues",
    description="Runs the deterministic medication safety analysis (duplicate therapy, allergy contraindications and known drug interactions) for the authenticated patient and returns the report without storing it.",
)
def check_medication_safety(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> MedicationSafetyReportResponse:
    patient = get_patient_for_user(current_user, db)
    report = get_medication_safety_service().analyze_patient_medications(
        db=db,
        patient_id=patient.id,
    )
    return _map_safety_report(report)


@router.post(
    "/analyze",
    response_model=MedicationSafetyAnalysisResponse,
    summary="Analyse and record the authenticated patient's medication safety findings",
    description="Runs the deterministic medication safety analysis for the authenticated patient, records the detected issues as clinical findings, and returns the report together with the number of records created, updated, unchanged and removed.",
)
def analyze_medication_safety(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> MedicationSafetyAnalysisResponse:
    patient = get_patient_for_user(current_user, db)
    result = get_medication_safety_persistence_service().analyze_and_persist(
        db=db,
        patient_id=patient.id,
    )
    return _map_analysis_response(result)
