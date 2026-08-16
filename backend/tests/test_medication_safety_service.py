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
from app.services.medication_safety_service import (
    FINDING_TYPE_ALLERGY,
    FINDING_TYPE_DOSAGE,
    FINDING_TYPE_DUPLICATE,
    FINDING_TYPE_INTERACTION,
    MedicationSafetyService,
    get_medication_safety_service,
    is_prescription_active,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

REFERENCE_DATE = date(2026, 6, 15)


class MedicationSafetyServiceTestCase(unittest.TestCase):
    """
    Unit tests for the deterministic medication safety analysis service.
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
        self.service = MedicationSafetyService()

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

    def _add_medication(self, name, normalized_name, patient=None):
        """Creates a Medication record for the given (or default) patient."""
        medication = Medication(
            id=uuid.uuid4(),
            patient_id=(patient or self.patient).id,
            name=name,
            normalized_name=normalized_name,
        )
        self.db.add(medication)
        self.db.commit()
        return medication

    def _add_prescription(self, medication, end_date=None, patient=None, dosage="10mg"):
        """Creates a Prescription record linked to the given medication."""
        prescription = Prescription(
            id=uuid.uuid4(),
            patient_id=(patient or self.patient).id,
            medication_id=medication.id,
            dosage=dosage,
            frequency="once daily",
            start_date=REFERENCE_DATE - timedelta(days=30),
            end_date=end_date,
        )
        self.db.add(prescription)
        self.db.commit()
        return prescription

    def _add_allergy(self, medication_name, normalized_name, severity=None, reaction=None):
        """Creates an Allergy record for the default patient."""
        allergy = Allergy(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            medication_name=medication_name,
            normalized_medication_name=normalized_name,
            reaction=reaction,
            severity=severity,
        )
        self.db.add(allergy)
        self.db.commit()
        return allergy

    def _analyze(self):
        """Runs the service against the default patient at a fixed reference date."""
        return self.service.analyze_patient_medications(
            db=self.db,
            patient_id=self.patient.id,
            reference_date=REFERENCE_DATE,
        )

    # ------------------------------------------------------------------
    # Active prescription rule
    # ------------------------------------------------------------------

    def test_prescription_with_null_end_date_is_active(self):
        """A prescription with no end date is treated as ongoing."""
        medication = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_prescription(medication, end_date=None)

        report = self._analyze()
        self.assertEqual(report.active_medications, ("warfarin",))

    def test_prescription_ending_today_is_active(self):
        """end_date equal to the reference date is still active."""
        medication = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_prescription(medication, end_date=REFERENCE_DATE)

        report = self._analyze()
        self.assertEqual(report.active_medications, ("warfarin",))

    def test_expired_prescription_is_excluded(self):
        """A prescription that ended before the reference date is inactive."""
        medication = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_prescription(medication, end_date=REFERENCE_DATE - timedelta(days=1))

        report = self._analyze()
        self.assertEqual(report.active_medications, ())
        self.assertEqual(report.finding_count, 0)

    def test_medication_without_prescriptions_is_active(self):
        """A medication with no prescription records is treated as active."""
        self._add_medication("Warfarin 5mg", "warfarin")

        report = self._analyze()
        self.assertEqual(report.active_medications, ("warfarin",))

    def test_is_prescription_active_helper(self):
        """The active-prescription rule is exposed and behaves consistently."""
        medication = self._add_medication("Warfarin 5mg", "warfarin")
        ongoing = self._add_prescription(medication, end_date=None)
        ending_today = self._add_prescription(medication, end_date=REFERENCE_DATE)
        expired = self._add_prescription(medication, end_date=REFERENCE_DATE - timedelta(days=1))

        self.assertTrue(is_prescription_active(ongoing, REFERENCE_DATE))
        self.assertTrue(is_prescription_active(ending_today, REFERENCE_DATE))
        self.assertFalse(is_prescription_active(expired, REFERENCE_DATE))

    # ------------------------------------------------------------------
    # A. Duplicate medication detection
    # ------------------------------------------------------------------

    def test_duplicate_medication_detected_once(self):
        """Two medication records sharing a normalized name yield one finding."""
        self._add_medication("Warfarin 5mg", "warfarin")
        self._add_medication("Coumadin (Warfarin)", "warfarin")

        report = self._analyze()
        duplicates = [f for f in report.findings if f.finding_type == FINDING_TYPE_DUPLICATE]

        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].risk_level, "medium")
        self.assertEqual(len(duplicates[0].medication_ids), 2)

    def test_duplicate_detected_from_multiple_active_prescriptions(self):
        """Two active prescriptions for the same medication are a duplicate."""
        medication = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_prescription(medication, end_date=None)
        self._add_prescription(medication, end_date=None)

        report = self._analyze()
        duplicates = [f for f in report.findings if f.finding_type == FINDING_TYPE_DUPLICATE]

        self.assertEqual(len(duplicates), 1)

    def test_expired_duplicate_prescription_not_reported(self):
        """A stopped prescription does not count towards duplicate therapy."""
        medication = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_prescription(medication, end_date=None)
        self._add_prescription(medication, end_date=REFERENCE_DATE - timedelta(days=10))

        report = self._analyze()
        duplicates = [f for f in report.findings if f.finding_type == FINDING_TYPE_DUPLICATE]

        self.assertEqual(duplicates, [])

    def test_single_medication_is_not_a_duplicate(self):
        """A single medication with one active prescription is not flagged."""
        medication = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_prescription(medication, end_date=None)

        report = self._analyze()
        self.assertEqual(report.finding_count, 0)

    # ------------------------------------------------------------------
    # B. Allergy contraindication
    # ------------------------------------------------------------------

    def test_allergy_contraindication_detected(self):
        """An active medication matching a documented allergy is flagged."""
        medication = self._add_medication("Amoxicillin 500mg", "amoxicillin")
        self._add_prescription(medication, end_date=None)
        self._add_allergy("Amoxicillin", "amoxicillin", severity="severe", reaction="Rash")

        report = self._analyze()
        allergies = [f for f in report.findings if f.finding_type == FINDING_TYPE_ALLERGY]

        self.assertEqual(len(allergies), 1)
        self.assertEqual(allergies[0].risk_level, "high")
        self.assertIn("Amoxicillin", allergies[0].description)
        self.assertIn("Rash", allergies[0].description)

    def test_mild_allergy_maps_to_medium_risk(self):
        """A documented mild reaction is reported at medium risk."""
        medication = self._add_medication("Amoxicillin 500mg", "amoxicillin")
        self._add_allergy("Amoxicillin", "amoxicillin", severity="mild")

        report = self._analyze()
        allergies = [f for f in report.findings if f.finding_type == FINDING_TYPE_ALLERGY]

        self.assertEqual(len(allergies), 1)
        self.assertEqual(allergies[0].risk_level, "medium")

    def test_unknown_allergy_severity_fails_safe_to_high(self):
        """An allergy with no recorded severity is treated as high risk."""
        medication = self._add_medication("Amoxicillin 500mg", "amoxicillin")
        self._add_allergy("Amoxicillin", "amoxicillin", severity=None)

        report = self._analyze()
        allergies = [f for f in report.findings if f.finding_type == FINDING_TYPE_ALLERGY]

        self.assertEqual(len(allergies), 1)
        self.assertEqual(allergies[0].risk_level, "high")

    def test_allergy_for_stopped_medication_not_reported(self):
        """An allergy is only flagged against currently active medications."""
        medication = self._add_medication("Amoxicillin 500mg", "amoxicillin")
        self._add_prescription(medication, end_date=REFERENCE_DATE - timedelta(days=5))
        self._add_allergy("Amoxicillin", "amoxicillin", severity="severe")

        report = self._analyze()
        self.assertEqual(report.finding_count, 0)

    def test_unrelated_allergy_not_reported(self):
        """An allergy to a medication the patient is not taking is ignored."""
        self._add_medication("Warfarin 5mg", "warfarin")
        self._add_allergy("Penicillin", "penicillin", severity="severe")

        report = self._analyze()
        self.assertEqual(report.finding_count, 0)

    # ------------------------------------------------------------------
    # C. Drug-drug interactions
    # ------------------------------------------------------------------

    def test_known_interaction_detected(self):
        """A known interacting pair of active medications is flagged."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        aspirin = self._add_medication("Aspirin 75mg", "aspirin")
        self._add_prescription(warfarin, end_date=None)
        self._add_prescription(aspirin, end_date=None)

        report = self._analyze()
        interactions = [f for f in report.findings if f.finding_type == FINDING_TYPE_INTERACTION]

        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0].risk_level, "high")
        self.assertEqual(len(interactions[0].medication_ids), 2)
        self.assertIn("bleeding", interactions[0].description.lower())

    def test_interaction_not_reported_when_one_drug_is_stopped(self):
        """An interaction requires both medications to be currently active."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        aspirin = self._add_medication("Aspirin 75mg", "aspirin")
        self._add_prescription(warfarin, end_date=None)
        self._add_prescription(aspirin, end_date=REFERENCE_DATE - timedelta(days=1))

        report = self._analyze()
        interactions = [f for f in report.findings if f.finding_type == FINDING_TYPE_INTERACTION]

        self.assertEqual(interactions, [])

    def test_unknown_pair_produces_no_interaction(self):
        """Medications with no curated interaction are not flagged."""
        paracetamol = self._add_medication("Paracetamol 500mg", "paracetamol")
        vitamin_d = self._add_medication("Vitamin D 1000IU", "vitamin d")
        self._add_prescription(paracetamol, end_date=None)
        self._add_prescription(vitamin_d, end_date=None)

        report = self._analyze()
        self.assertEqual(report.finding_count, 0)

    def test_interaction_reported_once_per_pair(self):
        """A pair is reported once regardless of medication record order."""
        aspirin = self._add_medication("Aspirin 75mg", "aspirin")
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        ibuprofen = self._add_medication("Ibuprofen 400mg", "ibuprofen")
        for med in (aspirin, warfarin, ibuprofen):
            self._add_prescription(med, end_date=None)

        report = self._analyze()
        interactions = [f for f in report.findings if f.finding_type == FINDING_TYPE_INTERACTION]
        pairs = {tuple(sorted(f.medications)) for f in interactions}

        # warfarin+aspirin and warfarin+ibuprofen are known; aspirin+ibuprofen is not.
        self.assertEqual(len(interactions), 2)
        self.assertEqual(len(pairs), 2)

    # ------------------------------------------------------------------
    # D. Dosage ceilings
    # ------------------------------------------------------------------

    def _dosage_findings(self, report):
        """Filters a report down to its dosage findings."""
        return [f for f in report.findings if f.finding_type == FINDING_TYPE_DOSAGE]

    def test_safe_dosage_produces_no_finding(self):
        """A dose at or below the configured ceiling is not flagged."""
        for dosage in ("500mg", "1000 mg", "1 g"):
            with self.subTest(dosage=dosage):
                medication = self._add_medication("Paracetamol 500mg", "paracetamol")
                self._add_prescription(medication, dosage=dosage)

                report = self._analyze()
                self.assertEqual(self._dosage_findings(report), [])

                self.db.query(Prescription).delete()
                self.db.query(Medication).delete()
                self.db.commit()

    def test_dosage_above_ceiling_produces_finding(self):
        """A dose clearly above the ceiling is flagged."""
        medication = self._add_medication("Paracetamol 500mg", "paracetamol")
        self._add_prescription(medication, dosage="1500mg")

        report = self._analyze()
        dosage_findings = self._dosage_findings(report)

        self.assertEqual(len(dosage_findings), 1)
        self.assertEqual(dosage_findings[0].risk_level, "high")
        self.assertEqual(dosage_findings[0].kind, "dosage")
        self.assertIn("1500mg", dosage_findings[0].description)
        self.assertEqual(dosage_findings[0].medication_ids, (medication.id,))

    def test_dosage_above_ceiling_in_grams_produces_finding(self):
        """Doses recorded in grams are converted before comparison."""
        medication = self._add_medication("Paracetamol 500mg", "paracetamol")
        self._add_prescription(medication, dosage="2 g")

        report = self._analyze()
        dosage_findings = self._dosage_findings(report)

        self.assertEqual(len(dosage_findings), 1)
        self.assertIn("2000 mg", dosage_findings[0].description)

    def test_malformed_dosage_produces_no_finding(self):
        """An unreadable dosage is never reported as unsafe."""
        for dosage in (None, "", "as directed", "500-1000mg", "1,000 mg", "2 tablets"):
            with self.subTest(dosage=dosage):
                medication = self._add_medication("Paracetamol 500mg", "paracetamol")
                self._add_prescription(medication, dosage=dosage)

                report = self._analyze()
                self.assertEqual(self._dosage_findings(report), [])

                self.db.query(Prescription).delete()
                self.db.query(Medication).delete()
                self.db.commit()

    def test_medication_without_configured_ceiling_is_not_flagged(self):
        """Medications outside the ceiling dataset are never evaluated."""
        medication = self._add_medication("Vitamin D 1000IU", "vitamin d")
        self._add_prescription(medication, dosage="999999 mg")

        report = self._analyze()
        self.assertEqual(self._dosage_findings(report), [])

    def test_dosage_checked_across_multiple_medications(self):
        """Each over-dosed medication produces its own finding."""
        paracetamol = self._add_medication("Paracetamol 500mg", "paracetamol")
        ibuprofen = self._add_medication("Ibuprofen 400mg", "ibuprofen")
        amlodipine = self._add_medication("Amlodipine 5mg", "amlodipine")
        self._add_prescription(paracetamol, dosage="1500mg")
        self._add_prescription(ibuprofen, dosage="1200mg")
        self._add_prescription(amlodipine, dosage="5mg")

        report = self._analyze()
        dosage_findings = self._dosage_findings(report)
        subjects = {f.subject for f in dosage_findings}

        self.assertEqual(len(dosage_findings), 2)
        self.assertEqual(subjects, {("paracetamol",), ("ibuprofen",)})

    def test_expired_prescription_dosage_is_ignored(self):
        """A dose on a stopped prescription is not evaluated."""
        medication = self._add_medication("Paracetamol 500mg", "paracetamol")
        self._add_prescription(
            medication,
            dosage="1500mg",
            end_date=REFERENCE_DATE - timedelta(days=1),
        )

        report = self._analyze()
        self.assertEqual(report.active_medications, ())
        self.assertEqual(self._dosage_findings(report), [])

    def test_only_active_prescription_dosage_is_evaluated(self):
        """A stopped high dose alongside an active safe dose is not flagged."""
        medication = self._add_medication("Paracetamol 500mg", "paracetamol")
        self._add_prescription(medication, dosage="500mg")
        self._add_prescription(
            medication,
            dosage="4000mg",
            end_date=REFERENCE_DATE - timedelta(days=1),
        )

        report = self._analyze()
        self.assertEqual(self._dosage_findings(report), [])

    def test_worst_active_dose_is_reported(self):
        """When several active doses exceed the ceiling, the highest is reported."""
        medication = self._add_medication("Paracetamol 500mg", "paracetamol")
        self._add_prescription(medication, dosage="1500mg")
        self._add_prescription(medication, dosage="3 g")

        report = self._analyze()
        dosage_findings = self._dosage_findings(report)

        self.assertEqual(len(dosage_findings), 1)
        self.assertIn("3000 mg", dosage_findings[0].description)

    def test_dosage_finding_identity_is_stable(self):
        """The dosage finding keeps its identity across analyses and labels."""
        medication = self._add_medication("Paracetamol 500mg", "paracetamol")
        self._add_prescription(medication, dosage="1500mg")

        first = self._dosage_findings(self._analyze())[0]

        # The same drug re-recorded from another document under a brand name.
        other = self._add_medication("Panadol (Paracetamol)", "paracetamol")
        self._add_prescription(other, dosage="1500mg")
        second = self._dosage_findings(self._analyze())[0]

        self.assertEqual(first.issue_key, "dosage_exceeded:paracetamol")
        self.assertEqual(first.issue_key, second.issue_key)
        self.assertEqual(first.title, second.title)

    def test_dosage_isolation_between_patients(self):
        """A dose recorded for another patient is never evaluated."""
        other_user = User(id=uuid.uuid4(), email=f"other_{uuid.uuid4().hex[:8]}@example.com")
        self.db.add(other_user)
        self.db.commit()
        other_patient = Patient(id=uuid.uuid4(), user_id=other_user.id)
        self.db.add(other_patient)
        self.db.commit()

        other_med = self._add_medication(
            "Paracetamol 500mg", "paracetamol", patient=other_patient
        )
        self._add_prescription(other_med, dosage="4000mg", patient=other_patient)

        own_med = self._add_medication("Paracetamol 500mg", "paracetamol")
        self._add_prescription(own_med, dosage="500mg")

        report = self._analyze()
        self.assertEqual(self._dosage_findings(report), [])
        self.assertEqual(report.finding_count, 0)

    def test_dosage_finding_coexists_with_other_checks(self):
        """A dosage finding does not disturb interaction detection."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        aspirin = self._add_medication("Aspirin 75mg", "aspirin")
        self._add_prescription(warfarin, dosage="15mg")
        self._add_prescription(aspirin, dosage="75mg")

        report = self._analyze()
        types = sorted(f.finding_type for f in report.findings)

        self.assertEqual(types, [FINDING_TYPE_DOSAGE, FINDING_TYPE_INTERACTION])

    # ------------------------------------------------------------------
    # Report structure, ordering and isolation
    # ------------------------------------------------------------------

    def test_report_is_ordered_by_severity(self):
        """Findings are returned most severe first."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        aspirin = self._add_medication("Aspirin 75mg", "aspirin")
        self._add_prescription(warfarin, end_date=None)
        self._add_prescription(aspirin, end_date=None)
        self._add_medication("Aspirin (generic)", "aspirin")

        report = self._analyze()
        risk_levels = [f.risk_level for f in report.findings]

        self.assertEqual(risk_levels[0], "high")
        self.assertEqual(report.highest_risk_level, "high")
        self.assertIn("medium", risk_levels)

    def test_report_metadata(self):
        """The report echoes the patient, reference date and medication count."""
        self._add_medication("Warfarin 5mg", "warfarin")
        self._add_medication("Aspirin 75mg", "aspirin")

        report = self._analyze()

        self.assertEqual(report.patient_id, self.patient.id)
        self.assertEqual(report.reference_date, REFERENCE_DATE)
        self.assertEqual(report.active_medication_count, 2)
        self.assertEqual(report.active_medications, ("aspirin", "warfarin"))

    def test_empty_patient_returns_empty_report(self):
        """A patient with no medications produces an empty report."""
        report = self._analyze()

        self.assertEqual(report.active_medications, ())
        self.assertEqual(report.findings, ())
        self.assertIsNone(report.highest_risk_level)

    def test_analysis_is_deterministic(self):
        """Repeated analysis of unchanged data yields an identical report."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        aspirin = self._add_medication("Aspirin 75mg", "aspirin")
        self._add_prescription(warfarin, end_date=None)
        self._add_prescription(aspirin, end_date=None)
        self._add_allergy("Warfarin", "warfarin", severity="moderate")

        first = self._analyze()
        second = self._analyze()

        self.assertEqual(first.findings, second.findings)

    def test_other_patients_records_are_not_analysed(self):
        """Only the requested patient's medications and allergies are considered."""
        other_user = User(id=uuid.uuid4(), email=f"other_{uuid.uuid4().hex[:8]}@example.com")
        self.db.add(other_user)
        self.db.commit()
        other_patient = Patient(id=uuid.uuid4(), user_id=other_user.id)
        self.db.add(other_patient)
        self.db.commit()

        # The other patient takes an interacting combination.
        other_warfarin = self._add_medication("Warfarin 5mg", "warfarin", patient=other_patient)
        other_aspirin = self._add_medication("Aspirin 75mg", "aspirin", patient=other_patient)
        self._add_prescription(other_warfarin, end_date=None, patient=other_patient)
        self._add_prescription(other_aspirin, end_date=None, patient=other_patient)

        # Our patient takes only one of them.
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        self._add_prescription(warfarin, end_date=None)

        report = self._analyze()

        self.assertEqual(report.active_medications, ("warfarin",))
        self.assertEqual(report.finding_count, 0)

    def test_service_does_not_persist_findings(self):
        """The service is read-only: no Finding rows are written."""
        warfarin = self._add_medication("Warfarin 5mg", "warfarin")
        aspirin = self._add_medication("Aspirin 75mg", "aspirin")
        self._add_prescription(warfarin, end_date=None)
        self._add_prescription(aspirin, end_date=None)

        report = self._analyze()

        self.assertGreater(report.finding_count, 0)
        self.assertEqual(self.db.query(Finding).count(), 0)

    def test_singleton_getter_returns_same_instance(self):
        """get_medication_safety_service returns a shared singleton."""
        self.assertIs(get_medication_safety_service(), get_medication_safety_service())


if __name__ == "__main__":
    unittest.main()
