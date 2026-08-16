"""
Persistence layer for the Medication Safety & Clinical Contraindication Engine.

Design Principles:
- Separation of concerns: MedicationSafetyService decides *what* is unsafe;
  this service decides *how* it is stored. The analysis itself stays pure and
  side-effect free.
- Reuses the existing Finding model: safety issues are ordinary findings. No
  new model, table, column or migration is introduced.
- Idempotent: Re-running the analysis reconciles the patient's existing safety
  findings instead of appending duplicates.
- Scoped: Only findings whose finding_type belongs to this engine
  (SAFETY_FINDING_TYPES) are ever read, updated or removed. Findings created by
  document extraction or any other source are never touched.
- Tenant-safe: patient_id is supplied by the API layer after authentication and
  is applied to every query and every row written.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.services.medication_safety_service import (
    SAFETY_FINDING_TYPES,
    MedicationSafetyFinding,
    MedicationSafetyReport,
    MedicationSafetyService,
    get_medication_safety_service,
)

logger = logging.getLogger(__name__)

# Column limits from the Finding model, applied defensively so an unusually long
# medication name can never overflow the column on PostgreSQL.
_FINDING_TYPE_MAX_LENGTH = 100
_TITLE_MAX_LENGTH = 255


@dataclass(frozen=True)
class MedicationSafetyPersistenceResult:
    """
    Outcome of persisting a medication safety report.

    Attributes:
        report: The analysis result that was persisted.
        created: Number of new Finding rows inserted.
        updated: Number of existing safety findings whose content changed.
        unchanged: Number of safety findings that were already up to date.
        removed: Number of stale safety findings deleted (resolved issues and
            any pre-existing duplicate rows for the same issue).
    """
    report: MedicationSafetyReport
    created: int
    updated: int
    unchanged: int
    removed: int

    @property
    def counts(self) -> Dict[str, int]:
        """Persistence counts as a plain dictionary, for logging and responses."""
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "removed": self.removed,
        }


class MedicationSafetyPersistenceService:
    """
    Service that stores medication safety findings in the existing Finding table.

    Safety findings are reconciled rather than appended: each detected issue is
    identified by (patient_id, finding_type, title), so repeatedly analysing the
    same medication list keeps exactly one Finding row per issue.
    """

    def __init__(
        self,
        safety_service: Optional[MedicationSafetyService] = None,
    ):
        """
        Initialize the service with an optional custom analysis service for
        dependency injection.
        """
        self.safety_service = safety_service or get_medication_safety_service()

    def analyze_and_persist(
        self,
        db: Session,
        patient_id: UUID,
        reference_date: Optional[date] = None,
        remove_resolved: bool = True,
    ) -> MedicationSafetyPersistenceResult:
        """
        Runs the deterministic safety analysis and persists its findings.

        Args:
            db: Active SQLAlchemy session.
            patient_id: UUID of the patient, resolved from the authenticated
                user by the API layer. Never accepted from client input.
            reference_date: Date used to evaluate prescription activity
                (defaults to today).
            remove_resolved: When True, safety findings that no longer apply are
                deleted so stale warnings do not linger. Only findings owned by
                this engine are eligible for deletion.

        Returns:
            MedicationSafetyPersistenceResult with the report and row counts.
        """
        report = self.safety_service.analyze_patient_medications(
            db=db,
            patient_id=patient_id,
            reference_date=reference_date,
        )
        return self.persist_report(
            db=db,
            patient_id=patient_id,
            report=report,
            remove_resolved=remove_resolved,
        )

    def persist_report(
        self,
        db: Session,
        patient_id: UUID,
        report: MedicationSafetyReport,
        remove_resolved: bool = True,
    ) -> MedicationSafetyPersistenceResult:
        """
        Persists an already computed safety report into the Finding table.

        Args:
            db: Active SQLAlchemy session.
            patient_id: UUID of the patient owning the findings.
            report: Report produced by MedicationSafetyService.
            remove_resolved: When True, stale safety findings are deleted.

        Returns:
            MedicationSafetyPersistenceResult with the report and row counts.

        Raises:
            ValueError: If the report was generated for a different patient.
        """
        if report.patient_id != patient_id:
            raise ValueError(
                "Safety report patient does not match the requested patient; refusing to persist."
            )

        existing, duplicate_rows = self._load_existing_safety_findings(db, patient_id)

        created = 0
        updated = 0
        unchanged = 0
        detected_keys = set()

        try:
            for finding in report.findings:
                key = _finding_key(finding)
                detected_keys.add(key)

                row = existing.get(key)
                if row is None:
                    db.add(_build_finding(patient_id, finding))
                    created += 1
                elif _apply_updates(row, finding):
                    updated += 1
                else:
                    unchanged += 1

            removed = 0
            if remove_resolved:
                stale = [row for key, row in existing.items() if key not in detected_keys]
                for row in (*stale, *duplicate_rows):
                    db.delete(row)
                    removed += 1

            db.commit()

            result = MedicationSafetyPersistenceResult(
                report=report,
                created=created,
                updated=updated,
                unchanged=unchanged,
                removed=removed,
            )
            logger.info(
                "Persisted medication safety findings for patient %s: %s",
                patient_id,
                result.counts,
            )
            return result

        except Exception as e:
            db.rollback()
            # Nothing but the exception type is logged. Identifiers and driver
            # messages can carry patient data (medication names, finding text,
            # row values), none of which may reach the logs.
            logger.error(
                "Failed to persist medication safety findings: %s",
                type(e).__name__,
            )
            raise

    def _load_existing_safety_findings(
        self,
        db: Session,
        patient_id: UUID,
    ) -> Tuple[Dict[Tuple[str, str], Finding], List[Finding]]:
        """
        Loads the patient's existing safety findings, keyed by issue identity.

        Only finding types owned by this engine are read, so findings from
        document extraction or other sources are left untouched.

        Args:
            db: Active SQLAlchemy session.
            patient_id: UUID of the patient owning the findings.

        Returns:
            Tuple of (mapping from (finding_type, title) to the row that
            represents that issue, list of any surplus rows describing an issue
            that is already represented).
        """
        rows = (
            db.query(Finding)
            .filter(
                Finding.patient_id == patient_id,
                Finding.finding_type.in_(SAFETY_FINDING_TYPES),
            )
            .order_by(Finding.created_at.asc())
            .all()
        )

        existing: Dict[Tuple[str, str], Finding] = {}
        surplus: List[Finding] = []
        for row in rows:
            key = (row.finding_type, row.title)
            if key in existing:
                # Defensive: collapse rows written before reconciliation existed.
                surplus.append(row)
            else:
                existing[key] = row

        return existing, surplus


def _finding_key(finding: MedicationSafetyFinding) -> Tuple[str, str]:
    """
    Returns the stable identity of a safety issue as stored in the database.

    The Finding model has no dedicated key column, so identity is the
    (finding_type, title) pair. Titles are derived from normalized medication
    names, which keeps this key stable across analyses.
    """
    return (
        _truncate(finding.finding_type, _FINDING_TYPE_MAX_LENGTH),
        _truncate(finding.title, _TITLE_MAX_LENGTH),
    )


def _build_finding(patient_id: UUID, finding: MedicationSafetyFinding) -> Finding:
    """
    Maps a MedicationSafetyFinding onto a new Finding row for the given patient.
    """
    finding_type, title = _finding_key(finding)
    return Finding(
        patient_id=patient_id,
        finding_type=finding_type,
        title=title,
        description=finding.description,
        risk_level=finding.risk_level,
        confidence=finding.confidence,
        recommendation=finding.recommendation,
    )


def _apply_updates(row: Finding, finding: MedicationSafetyFinding) -> bool:
    """
    Refreshes a stored finding in place if the analysis produced new content.

    Args:
        row: Existing Finding record for this issue.
        finding: Freshly analysed version of the same issue.

    Returns:
        True if any column changed, False if the record was already current.
    """
    changed = False
    updates = {
        "description": finding.description,
        "risk_level": finding.risk_level,
        "confidence": finding.confidence,
        "recommendation": finding.recommendation,
    }

    for column, value in updates.items():
        if getattr(row, column) != value:
            setattr(row, column, value)
            changed = True

    return changed


def _truncate(value: str, max_length: int) -> str:
    """
    Trims a value to the width of its database column.
    """
    return value if len(value) <= max_length else value[:max_length]


_default_medication_safety_persistence_service: Optional[MedicationSafetyPersistenceService] = None


def get_medication_safety_persistence_service() -> MedicationSafetyPersistenceService:
    """
    Returns a shared singleton instance of MedicationSafetyPersistenceService.
    """
    global _default_medication_safety_persistence_service
    if _default_medication_safety_persistence_service is None:
        _default_medication_safety_persistence_service = MedicationSafetyPersistenceService()
    return _default_medication_safety_persistence_service
