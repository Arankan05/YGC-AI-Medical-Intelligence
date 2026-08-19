import logging
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import AIAnalysis
from app.models.allergy import Allergy
from app.models.finding import Finding
from app.models.lab_result import LabResult
from app.models.medical_event import MedicalEvent
from app.models.medication import Medication
from app.models.prescription import Prescription
from app.schemas.extraction import ExtractedMedicalRecord

logger = logging.getLogger(__name__)


class MedicalPersistenceService:
    """
    Service for persisting extracted structured medical entities into PostgreSQL / SQLAlchemy models.
    Guarantees atomic transactions and handles entity deduplication (e.g. unique medications per patient).
    """

    def persist_extracted_record(
        self,
        db: Session,
        patient_id: UUID,
        document_id: UUID,
        extracted: ExtractedMedicalRecord,
    ) -> Dict[str, int]:
        """
        Persists all extracted clinical entities associated with a patient and source document.

        Args:
            db: Active SQLAlchemy session.
            patient_id: UUID of the patient owning the data.
            document_id: UUID of the document from which data was extracted.
            extracted: Structured ExtractedMedicalRecord object.

        Returns:
            Dictionary containing counts of records created for each entity type.
        """
        counts = {
            "events": 0,
            "medications": 0,
            "prescriptions": 0,
            "lab_results": 0,
            "allergies": 0,
            "findings": 0,
            "ai_analyses": 0,
        }

        try:
            # 1. Persist Medical Events
            for ev in extracted.events:
                event_record = MedicalEvent(
                    patient_id=patient_id,
                    document_id=document_id,
                    event_type=ev.event_type or "consultation",
                    event_date=ev.event_date,
                    title=ev.title,
                    description=ev.description,
                )
                db.add(event_record)
                counts["events"] += 1

            # 2. Persist Medications and Prescriptions with deduplication
            for med in extracted.medications:
                norm_name = (med.normalized_name or med.name).strip().lower()

                # Check if patient already has this medication
                existing_med = (
                    db.query(Medication)
                    .filter(
                        Medication.patient_id == patient_id,
                        Medication.normalized_name == norm_name,
                    )
                    .first()
                )

                if existing_med:
                    med_id = existing_med.id
                else:
                    new_med = Medication(
                        patient_id=patient_id,
                        name=med.name,
                        normalized_name=norm_name,
                    )
                    db.add(new_med)
                    db.flush()  # Generate UUID for new_med
                    med_id = new_med.id
                    counts["medications"] += 1

                # Create Prescription record linking to Medication and Document
                prescription_record = Prescription(
                    patient_id=patient_id,
                    document_id=document_id,
                    medication_id=med_id,
                    dosage=med.dosage,
                    frequency=med.frequency,
                    start_date=med.start_date,
                    end_date=med.end_date,
                    instructions=med.instructions,
                )
                db.add(prescription_record)
                counts["prescriptions"] += 1

            # 3. Persist Lab Results
            for lab in extracted.lab_results:
                lab_record = LabResult(
                    patient_id=patient_id,
                    document_id=document_id,
                    test_name=lab.test_name,
                    value=lab.value,
                    unit=lab.unit,
                    reference_range=lab.reference_range,
                    result_date=lab.result_date,
                )
                db.add(lab_record)
                counts["lab_results"] += 1

            # 4. Persist Allergies
            for al in extracted.allergies:
                norm_allergen = (al.normalized_medication_name or al.medication_name).strip().lower()
                allergy_record = Allergy(
                    patient_id=patient_id,
                    source_document_id=document_id,
                    medication_name=al.medication_name,
                    normalized_medication_name=norm_allergen,
                    reaction=al.reaction,
                    severity=al.severity,
                )
                db.add(allergy_record)
                counts["allergies"] += 1

            # 5. Persist Findings
            for fd in extracted.findings:
                finding_record = Finding(
                    patient_id=patient_id,
                    finding_type=fd.finding_type or "diagnosis",
                    title=fd.title,
                    description=fd.description,
                    risk_level=fd.risk_level,
                    confidence=fd.confidence,
                    recommendation=fd.recommendation,
                )
                db.add(finding_record)
                counts["findings"] += 1

            # 6. Persist or Update AI Analysis Record (Idempotent per document)
            str_doc_id = str(document_id)
            result_payload = {
                "document_id": str_doc_id,
                "summary": extracted.summary,
                "document_type_detected": extracted.document_type_detected,
                "confidence_score": extracted.confidence_score,
                "persisted_counts": counts,
            }

            existing_analyses = (
                db.query(AIAnalysis)
                .filter(
                    AIAnalysis.patient_id == patient_id,
                    AIAnalysis.analysis_type == "document_extraction",
                )
                .all()
            )

            existing_analysis = None
            for an in existing_analyses:
                if isinstance(an.result, dict) and an.result.get("document_id") == str_doc_id:
                    existing_analysis = an
                    break

            if existing_analysis:
                existing_analysis.result = result_payload
                existing_analysis.confidence = extracted.confidence_score
                counts["ai_analyses"] += 1
            else:
                analysis_record = AIAnalysis(
                    patient_id=patient_id,
                    analysis_type="document_extraction",
                    result=result_payload,
                    confidence=extracted.confidence_score,
                )
                db.add(analysis_record)
                counts["ai_analyses"] += 1

            db.commit()
            logger.info(
                "Persisted medical extraction for doc %s (patient %s): %s",
                document_id,
                patient_id,
                counts,
            )
            return counts

        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to persist extracted medical record for document %s: %s",
                document_id,
                str(e),
            )
            raise


_default_persistence_service: Optional[MedicalPersistenceService] = None


def get_medical_persistence_service() -> MedicalPersistenceService:
    """
    Returns a shared singleton instance of MedicalPersistenceService.
    """
    global _default_persistence_service
    if _default_persistence_service is None:
        _default_persistence_service = MedicalPersistenceService()
    return _default_persistence_service
