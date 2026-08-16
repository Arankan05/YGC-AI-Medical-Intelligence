from datetime import date, timedelta
import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.allergy import Allergy
from app.models.finding import Finding
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.user import User
from app.services.medication_safety_persistence_service import (
    MedicationSafetyPersistenceService,
    get_medication_safety_persistence_service,
)
from app.services.medication_safety_service import (
    FINDING_TYPE_ALLERGY,
    FINDING_TYPE_DOSAGE,
    FINDING_TYPE_DUPLICATE,
    FINDING_TYPE_INTERACTION,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

REFERENCE_DATE = date(2026, 6, 15)


class MedicationSafetyPersistenceServiceTestCase(unittest.TestCase):
    """
    Unit tests for persisting medication safety findings into the Finding table.
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()
        self.service = MedicationSafetyPersistenceService()

        # Seed User & Patient
        self.user = User(
            id=uuid.uuid4(),
            email=f"patient_{uuid.uuid4().hex[:8]}@example.com",
        )
        self.db.add(self.user)
        self.db.commit()

        self.patient = Patient(
            id=uuid.uuid4(),
            user_id=self.user.id,
        )
        self.db.add(self.patient)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        # Clean up records
        self.db.query(Finding).delete()
        self.db.query(Allergy).delete()
        self.db.query(Prescription).delete()
        self.db.query(Medication).delete()
        self.db.query(Patient).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_patient(self):
        """Creates an additional User/Patient pair."""
        user = User(id=uuid.uuid4(), email=f"other_{uuid.uuid4().hex[:8]}@example.com")
        self.db.add(user)
        self.db.commit()
        patient = Patient(id=uuid.uuid4(), user_id=user.id)
        self.db.add(patient)
        self.db.commit()
        return patient

    def _add_medication(self, name, normalized_name, patient=None, end_date=None, dosage="10mg"):
        """Creates a Medication with one active prescription by default."""
        target = patient or self.patient
        medication = Medication(
            id=uuid.uuid4(),
            patient_id=target.id,
            name=name,
            normalized_name=normalized_name,
        )
        self.db.add(medication)
        self.db.commit()

        prescription = Prescription(
            id=uuid.uuid4(),
            patient_id=target.id,
            medication_id=medication.id,
            dosage=dosage,
            frequency="once daily",
            start_date=REFERENCE_DATE - timedelta(days=30),
            end_date=end_date,
        )
        self.db.add(prescription)
        self.db.commit()
        return medication

    def _add_allergy(self, medication_name, normalized_name, severity="severe", patient=None):
        """Creates an Allergy record for the given (or default) patient."""
        allergy = Allergy(
            id=uuid.uuid4(),
            patient_id=(patient or self.patient).id,
            medication_name=medication_name,
            normalized_medication_name=normalized_name,
            reaction="Rash",
            severity=severity,
        )
        self.db.add(allergy)
        self.db.commit()
        return allergy

    def _seed_interaction(self, patient=None):
        """Gives the patient an interacting warfarin + aspirin combination."""
        self._add_medication("Warfarin 5mg", "warfarin", patient=patient)
        self._add_medication("Aspirin 75mg", "aspirin", patient=patient)

    def _persist(self, patient=None, remove_resolved=True):
        """Runs analysis and persistence at a fixed reference date."""
        return self.service.analyze_and_persist(
            db=self.db,
            patient_id=(patient or self.patient).id,
            reference_date=REFERENCE_DATE,
            remove_resolved=remove_resolved,
        )

    def _findings(self, patient=None, finding_type=None):
        """Reads back the stored findings for a patient."""
        query = self.db.query(Finding).filter(
            Finding.patient_id == (patient or self.patient).id
        )
        if finding_type is not None:
            query = query.filter(Finding.finding_type == finding_type)
        return query.all()

    # ------------------------------------------------------------------
    # Finding creation
    # ------------------------------------------------------------------

    def test_interaction_finding_is_created(self):
        """A detected drug interaction is stored as a Finding row."""
        self._seed_interaction()

        result = self._persist()
        findings = self._findings(finding_type=FINDING_TYPE_INTERACTION)

        self.assertEqual(result.created, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].risk_level, "high")
        self.assertEqual(findings[0].title, "Drug interaction: Aspirin + Warfarin")
        self.assertIn("bleeding", findings[0].description.lower())
        self.assertIsNotNone(findings[0].recommendation)
        self.assertAlmostEqual(findings[0].confidence, 0.90)

    def test_allergy_finding_is_created(self):
        """A detected allergy conflict is stored as a Finding row."""
        self._add_medication("Amoxicillin 500mg", "amoxicillin")
        self._add_allergy("Amoxicillin", "amoxicillin", severity="severe")

        result = self._persist()
        findings = self._findings(finding_type=FINDING_TYPE_ALLERGY)

        self.assertEqual(result.created, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].risk_level, "high")
        self.assertEqual(findings[0].title, "Allergy contraindication: Amoxicillin")

    def test_duplicate_medication_finding_is_created(self):
        """A detected duplicate medication is stored as a Finding row."""
        self._add_medication("Warfarin 5mg", "warfarin")
        self._add_medication("Coumadin (Warfarin)", "warfarin")

        result = self._persist()
        findings = self._findings(finding_type=FINDING_TYPE_DUPLICATE)

        self.assertEqual(result.created, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].risk_level, "medium")

    def test_dosage_finding_is_created(self):
        """A dose above its configured ceiling is stored as a Finding row."""
        self._add_medication("Paracetamol 500mg", "paracetamol", dosage="1500mg")

        result = self._persist()
        findings = self._findings(finding_type=FINDING_TYPE_DOSAGE)

        self.assertEqual(result.created, 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].risk_level, "high")
        self.assertEqual(findings[0].title, "Dosage above usual maximum: Paracetamol")

    def test_repeated_analysis_does_not_duplicate_dosage_findings(self):
        """Dosage findings reconcile like every other safety finding."""
        self._add_medication("Paracetamol 500mg", "paracetamol", dosage="1500mg")

        first = self._persist()
        original_id = self._findings()[0].id
        second = self._persist()

        self.assertEqual(first.created, 1)
        self.assertEqual(second.created, 0)
        self.assertEqual(second.unchanged, 1)
        self.assertEqual(len(self._findings()), 1)
        self.assertEqual(self._findings()[0].id, original_id)

    def test_resolved_dosage_issue_is_removed(self):
        """Correcting the dose deletes the stale dosage finding."""
        medication = self._add_medication("Paracetamol 500mg", "paracetamol", dosage="1500mg")
        self._persist()
        self.assertEqual(len(self._findings()), 1)

        prescription = (
            self.db.query(Prescription)
            .filter(Prescription.medication_id == medication.id)
            .one()
        )
        prescription.dosage = "500mg"
        self.db.commit()

        result = self._persist()

        self.assertEqual(result.removed, 1)
        self.assertEqual(len(self._findings()), 0)

    def test_no_findings_created_when_no_safety_issues(self):
        """A clean medication list writes nothing to the Finding table."""
        self._add_medication("Paracetamol 500mg", "paracetamol")

        result = self._persist()

        self.assertEqual(result.created, 0)
        self.assertEqual(result.report.finding_count, 0)
        self.assertEqual(self.db.query(Finding).count(), 0)

    # ------------------------------------------------------------------
    # Duplicate prevention / idempotency
    # ------------------------------------------------------------------

    def test_repeated_analysis_does_not_duplicate_findings(self):
        """Running the analysis repeatedly keeps exactly one row per issue."""
        self._seed_interaction()

        first = self._persist()
        second = self._persist()
        third = self._persist()

        self.assertEqual(first.created, 1)
        self.assertEqual(second.created, 0)
        self.assertEqual(second.unchanged, 1)
        self.assertEqual(third.created, 0)
        self.assertEqual(len(self._findings()), 1)

    def test_repeated_analysis_reuses_the_same_row(self):
        """Reconciliation updates the original row rather than replacing it."""
        self._seed_interaction()

        self._persist()
        original_id = self._findings()[0].id

        self._persist()
        rows = self._findings()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, original_id)

    def test_duplicate_medication_label_variation_does_not_duplicate_finding(self):
        """Re-recording a medication under another name reuses the same finding."""
        self._seed_interaction()
        self._persist()
        original_id = self._findings(finding_type=FINDING_TYPE_INTERACTION)[0].id

        # The same aspirin, recorded again from another document under a brand name.
        self._add_medication("Disprin (Aspirin)", "aspirin")
        self._persist()

        interactions = self._findings(finding_type=FINDING_TYPE_INTERACTION)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0].id, original_id)

    def test_changed_risk_level_updates_existing_finding(self):
        """A changed analysis result refreshes the stored row in place."""
        self._add_medication("Amoxicillin 500mg", "amoxicillin")
        allergy = self._add_allergy("Amoxicillin", "amoxicillin", severity="severe")

        self._persist()
        original_id = self._findings()[0].id

        # Severity is corrected to mild, which lowers the risk level.
        allergy.severity = "mild"
        self.db.commit()
        result = self._persist()

        rows = self._findings()
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.created, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, original_id)
        self.assertEqual(rows[0].risk_level, "medium")

    def test_resolved_issue_is_removed(self):
        """A safety finding that no longer applies is deleted."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_medication("Aspirin 75mg", "aspirin")
        self._persist()
        self.assertEqual(len(self._findings()), 1)

        # The patient stops warfarin, so the interaction no longer applies.
        prescription = (
            self.db.query(Prescription)
            .filter(Prescription.medication_id == warfarin.id)
            .one()
        )
        prescription.end_date = REFERENCE_DATE - timedelta(days=1)
        self.db.commit()

        result = self._persist()

        self.assertEqual(result.removed, 1)
        self.assertEqual(len(self._findings()), 0)

    def test_resolved_issue_is_kept_when_removal_disabled(self):
        """With remove_resolved=False nothing is ever deleted."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_medication("Aspirin 75mg", "aspirin")
        self._persist()

        prescription = (
            self.db.query(Prescription)
            .filter(Prescription.medication_id == warfarin.id)
            .one()
        )
        prescription.end_date = REFERENCE_DATE - timedelta(days=1)
        self.db.commit()

        result = self._persist(remove_resolved=False)

        self.assertEqual(result.removed, 0)
        self.assertEqual(len(self._findings()), 1)

    def test_preexisting_duplicate_rows_are_collapsed(self):
        """Surplus rows describing the same issue are cleaned up."""
        self._seed_interaction()
        self._persist()

        stored = self._findings()[0]
        clone = Finding(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            finding_type=stored.finding_type,
            title=stored.title,
            description=stored.description,
            risk_level=stored.risk_level,
        )
        self.db.add(clone)
        self.db.commit()
        self.assertEqual(len(self._findings()), 2)

        result = self._persist()

        self.assertEqual(result.removed, 1)
        self.assertEqual(len(self._findings()), 1)

    # ------------------------------------------------------------------
    # Patient isolation and unrelated data
    # ------------------------------------------------------------------

    def test_findings_are_stored_against_the_correct_patient(self):
        """Every persisted finding belongs to the analysed patient."""
        self._seed_interaction()

        result = self._persist()
        rows = self.db.query(Finding).all()

        self.assertEqual(result.report.patient_id, self.patient.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].patient_id, self.patient.id)

    def test_other_patients_findings_are_not_affected(self):
        """Persisting for one patient leaves another patient's findings alone."""
        other_patient = self._add_patient()
        self._seed_interaction(patient=other_patient)
        self._persist(patient=other_patient)
        other_id = self._findings(patient=other_patient)[0].id

        # Our patient has an unrelated allergy conflict.
        self._add_medication("Amoxicillin 500mg", "amoxicillin")
        self._add_allergy("Amoxicillin", "amoxicillin")
        self._persist()

        other_rows = self._findings(patient=other_patient)
        own_rows = self._findings()

        self.assertEqual(len(other_rows), 1)
        self.assertEqual(other_rows[0].id, other_id)
        self.assertEqual(other_rows[0].finding_type, FINDING_TYPE_INTERACTION)
        self.assertEqual(len(own_rows), 1)
        self.assertEqual(own_rows[0].finding_type, FINDING_TYPE_ALLERGY)

    def test_unrelated_findings_are_preserved(self):
        """Findings from other sources are never updated or deleted."""
        diagnosis = Finding(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            finding_type="diagnosis",
            title="Acute Bronchitis",
            description="Infection of the bronchial tree",
            risk_level="medium",
        )
        self.db.add(diagnosis)
        self.db.commit()

        self._seed_interaction()
        self._persist()
        # Then resolve everything, which triggers stale removal.
        self.db.query(Prescription).delete()
        self.db.query(Medication).delete()
        self.db.commit()
        self._persist()

        remaining = self._findings()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].finding_type, "diagnosis")
        self.assertEqual(remaining[0].title, "Acute Bronchitis")

    def test_persist_report_rejects_mismatched_patient(self):
        """A report generated for another patient is refused."""
        other_patient = self._add_patient()
        self._seed_interaction(patient=other_patient)
        report = self.service.safety_service.analyze_patient_medications(
            db=self.db,
            patient_id=other_patient.id,
            reference_date=REFERENCE_DATE,
        )

        with self.assertRaises(ValueError):
            self.service.persist_report(
                db=self.db,
                patient_id=self.patient.id,
                report=report,
            )

        self.assertEqual(self.db.query(Finding).count(), 0)

    def test_singleton_getter_returns_same_instance(self):
        """get_medication_safety_persistence_service returns a shared singleton."""
        self.assertIs(
            get_medication_safety_persistence_service(),
            get_medication_safety_persistence_service(),
        )


if __name__ == "__main__":
    unittest.main()
