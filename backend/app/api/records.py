import logging
from typing import Any, List, Optional, cast

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_application_user
from app.db.database import get_db
from app.models.ai_analysis import AIAnalysis
from app.models.allergy import Allergy
from app.models.document import Document
from app.models.finding import Finding
from app.models.lab_result import LabResult
from app.models.medical_event import MedicalEvent
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.user import User
from app.schemas.records import (
    AIAnalysisRecordResponse,
    AllergyRecordResponse,
    FindingRecordResponse,
    LabResultRecordResponse,
    MedicalEventRecordResponse,
    MedicalOverviewResponse,
    MedicationRecordResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/records", tags=["medical_records"])


def get_patient_for_user(user: User, db: Session) -> Patient:
    """
    Resolves the Patient record for the authenticated application user,
    auto-provisioning a Patient record if one does not exist yet.
    """
    patient = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not patient:
        patient = Patient(user_id=user.id)
        db.add(patient)
        db.commit()
        db.refresh(patient)
    return patient


def _map_medication_response(med: Medication, pres: Optional[Prescription] = None) -> MedicationRecordResponse:
    """
    Helper to convert a Medication and optional Prescription into MedicationRecordResponse.
    """
    return MedicationRecordResponse(
        id=cast(Any, med.id),
        name=cast(Any, med.name),
        normalized_name=cast(Any, med.normalized_name),
        dosage=cast(Any, pres.dosage) if pres else None,
        frequency=cast(Any, pres.frequency) if pres else None,
        start_date=cast(Any, pres.start_date) if pres else None,
        end_date=cast(Any, pres.end_date) if pres else None,
        instructions=cast(Any, pres.instructions) if pres else None,
        source_document_id=cast(Any, pres.document_id) if pres else None,
        source_document_name=cast(Any, pres.document.file_name) if (pres and pres.document) else None,
        status="active" if (not pres or not pres.end_date) else "stopped",
        created_at=cast(Any, med.created_at),
    )


@router.get(
    "/overview",
    response_model=MedicalOverviewResponse,
    summary="Get consolidated medical records overview",
    description="Returns aggregate counts, latest clinical summary, recent events, active medications, and priority findings for the authenticated patient.",
)
def get_medical_overview(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> MedicalOverviewResponse:
    patient = get_patient_for_user(current_user, db)

    total_docs = db.query(Document).filter(Document.patient_id == patient.id).count()
    total_meds = db.query(Medication).filter(Medication.patient_id == patient.id).count()
    total_findings = db.query(Finding).filter(Finding.patient_id == patient.id).count()
    total_events = db.query(MedicalEvent).filter(MedicalEvent.patient_id == patient.id).count()
    total_lab = db.query(LabResult).filter(LabResult.patient_id == patient.id).count()
    total_allergies = db.query(Allergy).filter(Allergy.patient_id == patient.id).count()

    latest_analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.patient_id == patient.id)
        .order_by(AIAnalysis.created_at.desc())
        .first()
    )

    summary_text = None
    confidence_score = None
    if latest_analysis:
        confidence_score = latest_analysis.confidence
        if isinstance(latest_analysis.result, dict):
            summary_text = latest_analysis.result.get("summary")

    # Recent medical events
    raw_events = (
        db.query(MedicalEvent)
        .options(joinedload(MedicalEvent.document))
        .filter(MedicalEvent.patient_id == patient.id)
        .order_by(MedicalEvent.event_date.desc().nullslast(), MedicalEvent.created_at.desc())
        .limit(10)
        .all()
    )
    recent_events = [
        MedicalEventRecordResponse(
            id=cast(Any, ev.id),
            event_type=cast(Any, ev.event_type),
            event_date=cast(Any, ev.event_date),
            title=cast(Any, ev.title),
            description=cast(Any, ev.description),
            source_document_id=cast(Any, ev.document_id),
            source_document_name=cast(Any, ev.document.file_name) if ev.document else None,
            created_at=cast(Any, ev.created_at),
        )
        for ev in raw_events
    ]

    # Active medications with prescriptions
    raw_meds = (
        db.query(Medication)
        .options(joinedload(Medication.prescriptions).joinedload(Prescription.document))
        .filter(Medication.patient_id == patient.id)
        .order_by(Medication.created_at.desc())
        .all()
    )
    active_meds = []
    for med in raw_meds:
        latest_pres = med.prescriptions[-1] if med.prescriptions else None
        active_meds.append(_map_medication_response(med, latest_pres))

    # Priority findings
    raw_findings = (
        db.query(Finding)
        .filter(Finding.patient_id == patient.id)
        .order_by(Finding.created_at.desc())
        .limit(10)
        .all()
    )
    priority_findings = [FindingRecordResponse.model_validate(f) for f in raw_findings]

    return MedicalOverviewResponse(
        patient_id=cast(Any, patient.id),
        total_documents=total_docs,
        total_medications=total_meds,
        total_findings=total_findings,
        total_events=total_events,
        total_lab_results=total_lab,
        total_allergies=total_allergies,
        latest_summary=summary_text,
        confidence_score=cast(Any, confidence_score),
        recent_events=recent_events,
        active_medications=active_meds,
        priority_findings=priority_findings,
    )


@router.get(
    "/medications",
    response_model=List[MedicationRecordResponse],
    summary="Get patient medications and prescriptions",
    description="Returns all medications and associated prescription administration details for the authenticated patient.",
)
def get_patient_medications(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> List[MedicationRecordResponse]:
    patient = get_patient_for_user(current_user, db)
    medications = (
        db.query(Medication)
        .options(joinedload(Medication.prescriptions).joinedload(Prescription.document))
        .filter(Medication.patient_id == patient.id)
        .order_by(Medication.created_at.desc())
        .all()
    )
    results = []
    for med in medications:
        latest_pres = med.prescriptions[-1] if med.prescriptions else None
        results.append(_map_medication_response(med, latest_pres))
    return results


@router.get(
    "/findings",
    response_model=List[FindingRecordResponse],
    summary="Get patient AI findings",
    description="Returns all clinical findings and AI safety assessments for the authenticated patient.",
)
def get_patient_findings(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> List[FindingRecordResponse]:
    patient = get_patient_for_user(current_user, db)
    findings = (
        db.query(Finding)
        .filter(Finding.patient_id == patient.id)
        .order_by(Finding.created_at.desc())
        .all()
    )
    return [FindingRecordResponse.model_validate(f) for f in findings]


@router.get(
    "/timeline",
    response_model=List[MedicalEventRecordResponse],
    summary="Get patient medical timeline events",
    description="Returns chronological medical events extracted from documents for the authenticated patient.",
)
def get_patient_timeline(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> List[MedicalEventRecordResponse]:
    patient = get_patient_for_user(current_user, db)
    events = (
        db.query(MedicalEvent)
        .options(joinedload(MedicalEvent.document))
        .filter(MedicalEvent.patient_id == patient.id)
        .order_by(MedicalEvent.event_date.desc().nullslast(), MedicalEvent.created_at.desc())
        .all()
    )
    return [
        MedicalEventRecordResponse(
            id=cast(Any, ev.id),
            event_type=cast(Any, ev.event_type),
            event_date=cast(Any, ev.event_date),
            title=cast(Any, ev.title),
            description=cast(Any, ev.description),
            source_document_id=cast(Any, ev.document_id),
            source_document_name=cast(Any, ev.document.file_name) if ev.document else None,
            created_at=cast(Any, ev.created_at),
        )
        for ev in events
    ]


@router.get(
    "/lab-results",
    response_model=List[LabResultRecordResponse],
    summary="Get patient lab results",
    description="Returns all laboratory diagnostic test records for the authenticated patient.",
)
def get_patient_lab_results(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> List[LabResultRecordResponse]:
    patient = get_patient_for_user(current_user, db)
    labs = (
        db.query(LabResult)
        .options(joinedload(LabResult.document))
        .filter(LabResult.patient_id == patient.id)
        .order_by(LabResult.result_date.desc().nullslast(), LabResult.created_at.desc())
        .all()
    )
    return [
        LabResultRecordResponse(
            id=cast(Any, lr.id),
            test_name=cast(Any, lr.test_name),
            value=cast(Any, lr.value),
            unit=cast(Any, lr.unit),
            reference_range=cast(Any, lr.reference_range),
            result_date=cast(Any, lr.result_date),
            source_document_id=cast(Any, lr.document_id),
            source_document_name=cast(Any, lr.document.file_name) if lr.document else None,
            created_at=cast(Any, lr.created_at),
        )
        for lr in labs
    ]


@router.get(
    "/allergies",
    response_model=List[AllergyRecordResponse],
    summary="Get patient drug allergies",
    description="Returns known drug allergies and adverse reaction records for the authenticated patient.",
)
def get_patient_allergies(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> List[AllergyRecordResponse]:
    patient = get_patient_for_user(current_user, db)
    allergies = (
        db.query(Allergy)
        .filter(Allergy.patient_id == patient.id)
        .order_by(Allergy.created_at.desc())
        .all()
    )
    return [AllergyRecordResponse.model_validate(a) for a in allergies]


@router.get(
    "/analyses",
    response_model=List[AIAnalysisRecordResponse],
    summary="Get patient AI analyses",
    description="Returns historical AI structured extraction and cross-check analysis logs for the authenticated patient.",
)
def get_patient_analyses(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
) -> List[AIAnalysisRecordResponse]:
    patient = get_patient_for_user(current_user, db)
    analyses = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.patient_id == patient.id)
        .order_by(AIAnalysis.created_at.desc())
        .all()
    )
    return [AIAnalysisRecordResponse.model_validate(an) for an in analyses]
