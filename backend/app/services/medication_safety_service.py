"""
Core analysis service for the Medication Safety & Clinical Contraindication Engine.

Design Principles:
- Deterministic: All checks are rule-based lookups over the patient's own
  records and the curated dataset in ``medication_interactions``. No AI provider
  or external API is consulted, so the same data always yields the same report.
- Read-only: This service never writes to the database. Persisting findings is
  handled separately.
- Tenant-safe: The service never resolves request context. The API layer
  resolves the authenticated user to a Patient and passes ``patient_id`` down;
  every query filters on it.
- Reuses existing models: Medication, Prescription and Allergy are read as-is.
  No new models, tables or columns are introduced.
"""

import logging
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.allergy import Allergy
from app.models.medication import Medication
from app.models.prescription import Prescription
from app.services.medication_dosage_rules import (
    DosageExceedance,
    check_dosage,
)
from app.services.medication_interactions import (
    MedicationInteraction,
    check_interaction,
    normalize_medication_name,
)

logger = logging.getLogger(__name__)

# Finding categories. The substrings "duplicate", "allergy" and "interaction"
# are recognised by the existing findings mapper in the frontend, so these
# values render without any frontend change.
FINDING_TYPE_DUPLICATE = "duplicate_medication"
FINDING_TYPE_ALLERGY = "allergy_contraindication"
FINDING_TYPE_INTERACTION = "drug_interaction"
FINDING_TYPE_DOSAGE = "dosage_exceeded"

# Every finding_type this engine owns. Persistence uses this set to scope its
# reads and deletes, so findings produced elsewhere are never touched.
SAFETY_FINDING_TYPES: Tuple[str, ...] = (
    FINDING_TYPE_DUPLICATE,
    FINDING_TYPE_ALLERGY,
    FINDING_TYPE_INTERACTION,
    FINDING_TYPE_DOSAGE,
)

# Maps each finding type onto the medication flag vocabulary the frontend
# already uses ("interaction", "duplicate", "dosage", "allergy"), so API
# responses need no new category enum on either side.
FINDING_TYPE_FLAG_KIND: Dict[str, str] = {
    FINDING_TYPE_DUPLICATE: "duplicate",
    FINDING_TYPE_ALLERGY: "allergy",
    FINDING_TYPE_INTERACTION: "interaction",
    FINDING_TYPE_DOSAGE: "dosage",
}

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

# Deterministic confidence scores per check. Rule-based matches on the patient's
# own records are more certain than heuristics, but never claim absolute truth.
_ALLERGY_CONFIDENCE = 0.95
_INTERACTION_CONFIDENCE = 0.90
_DUPLICATE_CONFIDENCE = 0.85
# Lower than the others: the ceiling dataset is a small demo set that does not
# model indication, patient age or organ function (see medication_dosage_rules).
_DOSAGE_CONFIDENCE = 0.70

# Maps the free-text Allergy.severity column onto a risk level. An allergy match
# is treated as high risk unless the documented reaction was explicitly mild,
# and unknown severities fail safe to high.
_ALLERGY_SEVERITY_RISK: Dict[str, str] = {
    "mild": RISK_MEDIUM,
    "minor": RISK_MEDIUM,
    "low": RISK_MEDIUM,
    "moderate": RISK_HIGH,
    "medium": RISK_HIGH,
    "severe": RISK_HIGH,
    "high": RISK_HIGH,
    "critical": RISK_HIGH,
    "life-threatening": RISK_HIGH,
    "life threatening": RISK_HIGH,
    "anaphylaxis": RISK_HIGH,
}

# Sort order for report output: most severe findings first.
_RISK_ORDER: Dict[str, int] = {RISK_HIGH: 0, RISK_MEDIUM: 1, RISK_LOW: 2}


@dataclass(frozen=True)
class MedicationSafetyFinding:
    """
    A single deterministic safety issue detected for a patient.

    Field names mirror the Finding model so the persistence step can map this
    onto a Finding row without translation.

    Attributes:
        finding_type: Category of the issue (duplicate, allergy, interaction).
        subject: Normalized names of the medications the issue is about. Together
            with finding_type this is the stable identity of the issue: it does
            not change when a medication is re-recorded under a different label,
            so repeated analyses of the same clinical situation match up.
        title: Short headline for the issue, derived from subject.
        description: Human-readable explanation of what was detected and why.
        risk_level: Clinical risk ("low", "medium" or "high").
        confidence: Deterministic confidence score between 0.0 and 1.0.
        recommendation: Suggested patient/clinician action.
        medications: Display names of the medications involved.
        medication_ids: IDs of the Medication records involved.
    """
    finding_type: str
    subject: Tuple[str, ...]
    title: str
    description: str
    risk_level: str
    confidence: float
    recommendation: Optional[str]
    medications: Tuple[str, ...]
    medication_ids: Tuple[UUID, ...]

    @property
    def kind(self) -> str:
        """
        Category in the flag vocabulary shared with the frontend
        ("duplicate", "allergy" or "interaction").
        """
        return FINDING_TYPE_FLAG_KIND.get(self.finding_type, self.finding_type)

    @property
    def issue_key(self) -> str:
        """
        Stable identifier for this issue, e.g. "drug_interaction:aspirin+warfarin".

        Derived from finding_type and subject, so the same clinical issue keeps
        the same key across analyses whether or not it has been persisted.
        """
        return f"{self.finding_type}:{'+'.join(self.subject)}"


@dataclass(frozen=True)
class MedicationSafetyReport:
    """
    Structured result of a medication safety analysis for one patient.

    Attributes:
        patient_id: Patient the report was generated for.
        reference_date: Date used to decide whether a prescription is active.
        active_medications: Normalized names of the medications analysed.
        findings: Detected safety issues, most severe first.
    """
    patient_id: UUID
    reference_date: date
    active_medications: Tuple[str, ...]
    findings: Tuple[MedicationSafetyFinding, ...]

    @property
    def active_medication_count(self) -> int:
        """Number of distinct active medications analysed."""
        return len(self.active_medications)

    @property
    def finding_count(self) -> int:
        """Total number of safety findings detected."""
        return len(self.findings)

    @property
    def highest_risk_level(self) -> Optional[str]:
        """Highest risk level present in the report, or None if no findings."""
        if not self.findings:
            return None
        return min(
            (f.risk_level for f in self.findings),
            key=lambda level: _RISK_ORDER.get(level, len(_RISK_ORDER)),
        )


@dataclass(frozen=True)
class _ActiveMedication:
    """
    Internal view of one Medication record that is currently being taken.

    Attributes:
        medication_id: ID of the Medication record.
        name: Medication name as recorded on the document.
        normalized_name: Canonical name used for all matching.
        active_prescription_count: Number of currently active prescriptions.
        active_dosages: Dosage strings recorded on the active prescriptions.
    """
    medication_id: UUID
    name: str
    normalized_name: str
    active_prescription_count: int
    active_dosages: Tuple[str, ...]


def is_prescription_active(
    prescription: Prescription,
    reference_date: Optional[date] = None,
) -> bool:
    """
    Determines whether a prescription is currently active.

    Rule:
    - end_date IS NULL  -> active (ongoing prescription)
    - end_date >= today -> active
    - end_date <  today -> inactive

    Args:
        prescription: Prescription record to evaluate.
        reference_date: Date to compare against (defaults to today).

    Returns:
        True if the prescription is active on the reference date.
    """
    end_date = prescription.end_date
    if end_date is None:
        return True
    return end_date >= (reference_date or date.today())


class MedicationSafetyService:
    """
    Service that analyses a patient's active medications for duplicate therapy,
    allergy contraindications and known drug-drug interactions.

    The service is stateless and read-only: it receives an already resolved
    patient_id from the API layer and never persists its results.
    """

    def analyze_patient_medications(
        self,
        db: Session,
        patient_id: UUID,
        reference_date: Optional[date] = None,
    ) -> MedicationSafetyReport:
        """
        Runs all deterministic safety checks for a single patient.

        Args:
            db: Active SQLAlchemy session.
            patient_id: UUID of the patient, resolved from the authenticated
                user by the API layer. Never accepted from client input.
            reference_date: Date used to evaluate prescription activity
                (defaults to today). Mainly useful for deterministic testing.

        Returns:
            MedicationSafetyReport containing the detected findings, ordered
            with the most severe first.
        """
        today = reference_date or date.today()

        active_medications = self._load_active_medications(db, patient_id, today)
        grouped = self._group_by_normalized_name(active_medications)

        findings: List[MedicationSafetyFinding] = []
        findings.extend(self._check_duplicates(grouped))
        findings.extend(self._check_allergies(db, patient_id, grouped))
        findings.extend(self._check_interactions(grouped))
        findings.extend(self._check_dosages(grouped))

        report = MedicationSafetyReport(
            patient_id=patient_id,
            reference_date=today,
            active_medications=tuple(sorted(grouped)),
            findings=tuple(sorted(findings, key=_finding_sort_key)),
        )

        logger.info(
            "Medication safety analysis for patient %s: %d active medications, %d findings",
            patient_id,
            report.active_medication_count,
            report.finding_count,
        )
        return report

    def _load_active_medications(
        self,
        db: Session,
        patient_id: UUID,
        reference_date: date,
    ) -> List[_ActiveMedication]:
        """
        Loads the patient's medications and keeps only those currently taken.

        A medication is considered active if it has at least one active
        prescription, or if it has no prescription records at all. This matches
        the active/stopped rule already used by the records API.

        Args:
            db: Active SQLAlchemy session.
            patient_id: UUID of the patient owning the records.
            reference_date: Date used to evaluate prescription activity.

        Returns:
            List of active medications, ordered deterministically by name.
        """
        medications = (
            db.query(Medication)
            .options(joinedload(Medication.prescriptions))
            .filter(Medication.patient_id == patient_id)
            .order_by(Medication.created_at.desc())
            .all()
        )

        active: List[_ActiveMedication] = []
        for med in medications:
            # Defensive tenant guard: only ever consider this patient's rows.
            prescriptions = [p for p in med.prescriptions if p.patient_id == patient_id]
            active_prescriptions = [
                p for p in prescriptions if is_prescription_active(p, reference_date)
            ]
            active_count = len(active_prescriptions)

            if prescriptions and active_count == 0:
                continue

            normalized = normalize_medication_name(med.normalized_name or med.name)
            if not normalized:
                continue

            active.append(
                _ActiveMedication(
                    medication_id=med.id,
                    name=med.name,
                    normalized_name=normalized,
                    active_prescription_count=active_count,
                    active_dosages=tuple(p.dosage for p in active_prescriptions if p.dosage),
                )
            )

        active.sort(key=lambda m: (m.normalized_name, m.name, str(m.medication_id)))
        return active

    def _group_by_normalized_name(
        self,
        medications: List[_ActiveMedication],
    ) -> Dict[str, List[_ActiveMedication]]:
        """
        Groups active medications by their normalized name.
        """
        grouped: Dict[str, List[_ActiveMedication]] = {}
        for med in medications:
            grouped.setdefault(med.normalized_name, []).append(med)
        return grouped

    def _check_duplicates(
        self,
        grouped: Dict[str, List[_ActiveMedication]],
    ) -> List[MedicationSafetyFinding]:
        """
        Detects duplicate therapy: the same medication recorded more than once.

        A duplicate is reported when a normalized medication name maps to more
        than one Medication record, or to more than one active prescription.
        Each normalized name produces at most one finding.

        Args:
            grouped: Active medications grouped by normalized name.

        Returns:
            One finding per duplicated medication.
        """
        findings: List[MedicationSafetyFinding] = []

        for normalized in sorted(grouped):
            entries = grouped[normalized]
            record_count = len(entries)
            prescription_count = sum(e.active_prescription_count for e in entries)

            if record_count <= 1 and prescription_count <= 1:
                continue

            display_name = _display_name(entries)
            variants = sorted({e.name for e in entries})
            variant_text = (
                f" It appears under the names: {', '.join(variants)}."
                if len(variants) > 1
                else ""
            )

            findings.append(
                MedicationSafetyFinding(
                    finding_type=FINDING_TYPE_DUPLICATE,
                    subject=(normalized,),
                    title=f"Duplicate medication: {_format_label(normalized)}",
                    description=(
                        f"{display_name} appears {record_count} time(s) in your medication list "
                        f"with {prescription_count} active prescription(s)."
                        f"{variant_text} Taking the same medicine twice can lead to an "
                        f"unintended double dose."
                    ),
                    risk_level=RISK_MEDIUM,
                    confidence=_DUPLICATE_CONFIDENCE,
                    recommendation=(
                        "Confirm with your doctor or pharmacist which prescription to follow, "
                        "so this medicine is not taken twice."
                    ),
                    medications=tuple(e.name for e in entries),
                    medication_ids=tuple(e.medication_id for e in entries),
                )
            )

        return findings

    def _check_allergies(
        self,
        db: Session,
        patient_id: UUID,
        grouped: Dict[str, List[_ActiveMedication]],
    ) -> List[MedicationSafetyFinding]:
        """
        Detects medications that match a documented allergy for the patient.

        Matching uses the existing Allergy fields only: the normalized allergen
        name is compared against the normalized medication name.

        Args:
            db: Active SQLAlchemy session.
            patient_id: UUID of the patient owning the records.
            grouped: Active medications grouped by normalized name.

        Returns:
            One finding per matching allergy record.
        """
        if not grouped:
            return []

        allergies = (
            db.query(Allergy)
            .filter(Allergy.patient_id == patient_id)
            .order_by(Allergy.created_at.desc())
            .all()
        )

        findings: List[MedicationSafetyFinding] = []
        for allergy in allergies:
            normalized_allergen = normalize_medication_name(
                allergy.normalized_medication_name or allergy.medication_name
            )
            entries = grouped.get(normalized_allergen)
            if not normalized_allergen or not entries:
                continue

            display_name = _display_name(entries)
            reaction_text = (
                f" Recorded reaction: {allergy.reaction}." if allergy.reaction else ""
            )
            severity_text = (
                f" Documented severity: {allergy.severity}." if allergy.severity else ""
            )

            findings.append(
                MedicationSafetyFinding(
                    finding_type=FINDING_TYPE_ALLERGY,
                    subject=(normalized_allergen,),
                    title=f"Allergy contraindication: {_format_label(normalized_allergen)}",
                    description=(
                        f"You are currently taking {display_name}, but a documented allergy to "
                        f"{allergy.medication_name} is on file.{reaction_text}{severity_text}"
                    ),
                    risk_level=_map_allergy_risk(allergy.severity),
                    confidence=_ALLERGY_CONFIDENCE,
                    recommendation=(
                        "Contact your doctor or pharmacist before taking the next dose to confirm "
                        "this medicine is safe for you."
                    ),
                    medications=tuple(e.name for e in entries),
                    medication_ids=tuple(e.medication_id for e in entries),
                )
            )

        return findings

    def _check_interactions(
        self,
        grouped: Dict[str, List[_ActiveMedication]],
    ) -> List[MedicationSafetyFinding]:
        """
        Detects known drug-drug interactions among the active medications.

        Every distinct pair of active medications is looked up in the curated
        dataset in medication_interactions. Interaction facts are never
        generated at runtime.

        Args:
            grouped: Active medications grouped by normalized name.

        Returns:
            One finding per interacting pair.
        """
        findings: List[MedicationSafetyFinding] = []

        for name_a, name_b in combinations(sorted(grouped), 2):
            interaction: Optional[MedicationInteraction] = check_interaction(name_a, name_b)
            if interaction is None:
                continue

            entries_a = grouped[name_a]
            entries_b = grouped[name_b]
            display_a = _display_name(entries_a)
            display_b = _display_name(entries_b)

            findings.append(
                MedicationSafetyFinding(
                    finding_type=FINDING_TYPE_INTERACTION,
                    subject=(name_a, name_b),
                    title=f"Drug interaction: {_format_label(name_a)} + {_format_label(name_b)}",
                    description=(
                        f"You are taking {display_a} and {display_b} at the same time. "
                        f"{interaction.description}"
                    ),
                    risk_level=interaction.severity,
                    confidence=_INTERACTION_CONFIDENCE,
                    recommendation=(
                        "Discuss this combination with your doctor or pharmacist before your "
                        "next dose."
                    ),
                    medications=(display_a, display_b),
                    medication_ids=tuple(
                        e.medication_id for e in (*entries_a, *entries_b)
                    ),
                )
            )

        return findings

    def _check_dosages(
        self,
        grouped: Dict[str, List[_ActiveMedication]],
    ) -> List[MedicationSafetyFinding]:
        """
        Detects prescribed doses that exceed their configured single-dose ceiling.

        Only medications present in the curated ceiling dataset are evaluated,
        and only doses that can be parsed unambiguously and compared in matching
        units. A dosage that cannot be read is skipped rather than assumed
        unsafe, so an unparseable string never produces a finding.

        Each normalized medication name produces at most one finding, describing
        the highest exceeding dose recorded for it.

        Args:
            grouped: Active medications grouped by normalized name.

        Returns:
            One finding per medication whose dose exceeds its ceiling.
        """
        findings: List[MedicationSafetyFinding] = []

        for normalized in sorted(grouped):
            entries = grouped[normalized]

            exceedances: List[DosageExceedance] = []
            for entry in entries:
                for dosage_text in entry.active_dosages:
                    exceedance = check_dosage(normalized, dosage_text)
                    if exceedance is not None:
                        exceedances.append(exceedance)

            if not exceedances:
                continue

            # Report the worst dose recorded for this medication; ties resolve on
            # the original text so the finding stays deterministic.
            worst = max(exceedances, key=lambda e: (e.dose.value, e.dose.original))
            display_name = _display_name(entries)

            findings.append(
                MedicationSafetyFinding(
                    finding_type=FINDING_TYPE_DOSAGE,
                    subject=(normalized,),
                    title=f"Dosage above usual maximum: {_format_label(normalized)}",
                    description=(
                        f"Your record lists {display_name} at {worst.dose.original}. "
                        f"{worst.description}"
                    ),
                    risk_level=worst.severity,
                    confidence=_DOSAGE_CONFIDENCE,
                    recommendation=(
                        "Check this dose with your doctor or pharmacist before taking it, in "
                        "case it was recorded incorrectly."
                    ),
                    medications=tuple(e.name for e in entries),
                    medication_ids=tuple(e.medication_id for e in entries),
                )
            )

        return findings


def _display_name(entries: List[_ActiveMedication]) -> str:
    """
    Returns the medication name to show for a group of duplicate records.
    """
    return entries[0].name


def _format_label(normalized_name: str) -> str:
    """
    Formats a normalized medication name for display in a finding title.

    Titles are built from normalized names rather than the names recorded on the
    source document, so the title of a given clinical issue stays identical
    across repeated analyses even if the medication is later re-recorded under a
    different label.
    """
    return normalized_name.title()


def _map_allergy_risk(severity: Optional[str]) -> str:
    """
    Maps the free-text Allergy.severity value onto a risk level.

    Unknown or missing severities fail safe to high risk, because an active
    medication matching a documented allergy always warrants review.
    """
    if not severity:
        return RISK_HIGH
    return _ALLERGY_SEVERITY_RISK.get(severity.strip().lower(), RISK_HIGH)


def _finding_sort_key(finding: MedicationSafetyFinding) -> Tuple[int, str, str]:
    """
    Deterministic report ordering: most severe first, then category, then title.
    """
    return (
        _RISK_ORDER.get(finding.risk_level, len(_RISK_ORDER)),
        finding.finding_type,
        finding.title,
    )


_default_medication_safety_service: Optional[MedicationSafetyService] = None


def get_medication_safety_service() -> MedicationSafetyService:
    """
    Returns a shared singleton instance of MedicationSafetyService.
    """
    global _default_medication_safety_service
    if _default_medication_safety_service is None:
        _default_medication_safety_service = MedicationSafetyService()
    return _default_medication_safety_service
