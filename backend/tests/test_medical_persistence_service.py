from datetime import date
import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
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
from app.schemas.extraction import (
    ExtractedAllergy,
    ExtractedFinding,
    ExtractedLabResult,
    ExtractedMedicalEvent,
    ExtractedMedicalRecord,
    ExtractedMedication,
)
from app.services.medical_persistence_service import MedicalPersistenceService

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class MedicalPersistenceServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()
        self.service = MedicalPersistenceService()

        # Seed User & Patient
        self.user = User(
            id=uuid.uuid4(),
            email=f"patient_{uuid.uuid4().hex[:8]}@example.com",
        )
        self.db.add(self.user)
        self.db.commit()

        self.patient_id: uuid.UUID = uuid.uuid4()
        self.patient = Patient(
            id=self.patient_id,
            user_id=self.user.id,
        )
        self.db.add(self.patient)
        self.db.commit()

        self.document_id: uuid.UUID = uuid.uuid4()
        self.document = Document(
            id=self.document_id,
            patient_id=self.patient_id,
            file_name="prescription.pdf",
            file_path="uploads/prescription.pdf",
            document_type="prescription",
            processing_status="COMPLETED",
            extracted_text="Sample extracted text",
        )
        self.db.add(self.document)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        # Clean up records
        self.db.query(AIAnalysis).delete()
        self.db.query(Finding).delete()
        self.db.query(Allergy).delete()
        self.db.query(LabResult).delete()
        self.db.query(Prescription).delete()
        self.db.query(Medication).delete()
        self.db.query(MedicalEvent).delete()
        self.db.query(Document).delete()
        self.db.query(Patient).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_persist_extracted_record_all_entities(self):
        extracted = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Patient treated for bacterial bronchitis.",
            confidence_score=0.94,
            events=[
                ExtractedMedicalEvent(
                    event_type="consultation",
                    event_date=date(2026, 4, 1),
                    title="Pulmonology Visit",
                    description="Chronic cough and wheezing",
                )
            ],
            medications=[
                ExtractedMedication(
                    name="Azithromycin 250mg",
                    normalized_name="azithromycin",
                    dosage="250mg",
                    frequency="once daily",
                    start_date=date(2026, 4, 1),
                    end_date=date(2026, 4, 5),
                    instructions="Take 500mg on day 1, then 250mg daily",
                )
            ],
            lab_results=[
                ExtractedLabResult(
                    test_name="Chest X-Ray",
                    value="Clear lung fields",
                    result_date=date(2026, 4, 1),
                )
            ],
            allergies=[
                ExtractedAllergy(
                    medication_name="Erythromycin",
                    reaction="Severe nausea",
                    severity="moderate",
                )
            ],
            findings=[
                ExtractedFinding(
                    finding_type="diagnosis",
                    title="Acute Bronchitis",
                    description="Infection of the bronchial tree",
                    risk_level="medium",
                    confidence=0.9,
                )
            ],
        )

        counts = self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=extracted,
        )

        assert counts["events"] == 1
        assert counts["medications"] == 1
        assert counts["prescriptions"] == 1
        assert counts["lab_results"] == 1
        assert counts["allergies"] == 1
        assert counts["findings"] == 1
        assert counts["ai_analyses"] == 1

        # Verify DB records
        events = self.db.query(MedicalEvent).filter(MedicalEvent.patient_id == self.patient.id).all()
        assert len(events) == 1
        assert events[0].title == "Pulmonology Visit"
        assert events[0].document_id == self.document.id

        meds = self.db.query(Medication).filter(Medication.patient_id == self.patient.id).all()
        assert len(meds) == 1
        assert meds[0].normalized_name == "azithromycin"

        prescs = self.db.query(Prescription).filter(Prescription.patient_id == self.patient.id).all()
        assert len(prescs) == 1
        assert prescs[0].medication_id == meds[0].id
        assert prescs[0].dosage == "250mg"

        labs = self.db.query(LabResult).filter(LabResult.patient_id == self.patient.id).all()
        assert len(labs) == 1
        assert labs[0].test_name == "Chest X-Ray"

        allergies = self.db.query(Allergy).filter(Allergy.patient_id == self.patient.id).all()
        assert len(allergies) == 1
        assert allergies[0].normalized_medication_name == "erythromycin"

        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient.id).all()
        assert len(findings) == 1
        assert findings[0].title == "Acute Bronchitis"

        analyses = self.db.query(AIAnalysis).filter(AIAnalysis.patient_id == self.patient.id).all()
        assert len(analyses) == 1
        assert analyses[0].analysis_type == "document_extraction"
        assert analyses[0].confidence == 0.94

    def test_medication_deduplication(self):
        # First extraction creates Medication 'amoxicillin'
        rec1 = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Initial Rx",
            confidence_score=0.9,
            medications=[
                ExtractedMedication(name="Amoxicillin 250mg", normalized_name="amoxicillin", dosage="250mg")
            ],
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec1,
        )

        meds_before = self.db.query(Medication).filter(Medication.patient_id == self.patient.id).all()
        assert len(meds_before) == 1

        # Second extraction for same patient with different dosage of same medication 'amoxicillin'
        rec2 = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Follow up Rx",
            confidence_score=0.9,
            medications=[
                ExtractedMedication(name="Amoxicillin 500mg", normalized_name="amoxicillin", dosage="500mg")
            ],
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec2,
        )

        meds_after = self.db.query(Medication).filter(Medication.patient_id == self.patient.id).all()
        assert len(meds_after) == 1  # Reused medication record, no duplicate!

        prescs_after = self.db.query(Prescription).filter(Prescription.patient_id == self.patient.id).all()
        assert len(prescs_after) == 2  # But 2 distinct prescriptions created!
        assert prescs_after[0].medication_id == meds_after[0].id
        assert prescs_after[1].medication_id == meds_after[0].id

    def test_ai_analysis_extraction_idempotency_same_document(self):
        # A. First extraction creates one AIAnalysis
        rec1 = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="First summary of document A",
            confidence_score=0.85,
        )
        counts1 = self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec1,
        )
        assert counts1["ai_analyses"] == 1

        analyses_1 = (
            self.db.query(AIAnalysis)
            .filter(
                AIAnalysis.patient_id == self.patient.id,
                AIAnalysis.analysis_type == "document_extraction",
            )
            .all()
        )
        assert len(analyses_1) == 1
        assert analyses_1[0].result.get("summary") == "First summary of document A"
        assert analyses_1[0].result.get("document_id") == str(self.document.id)

        # B & D. Second extraction for SAME document does NOT create another AIAnalysis & updates result
        rec2 = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Updated second summary of document A",
            confidence_score=0.92,
        )
        counts2 = self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec2,
        )
        assert counts2["ai_analyses"] == 1

        analyses_2 = (
            self.db.query(AIAnalysis)
            .filter(
                AIAnalysis.patient_id == self.patient.id,
                AIAnalysis.analysis_type == "document_extraction",
            )
            .all()
        )
        assert len(analyses_2) == 1  # Still exactly 1 row!
        assert analyses_2[0].result.get("summary") == "Updated second summary of document A"
        assert analyses_2[0].confidence == 0.92

        # C. Third extraction still leaves exactly one document_extraction analysis
        rec3 = ExtractedMedicalRecord(
            document_type_detected="consultation_note",
            summary="Third summary of document A",
            confidence_score=0.95,
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec3,
        )
        analyses_3 = (
            self.db.query(AIAnalysis)
            .filter(
                AIAnalysis.patient_id == self.patient.id,
                AIAnalysis.analysis_type == "document_extraction",
            )
            .all()
        )
        assert len(analyses_3) == 1  # Still exactly 1 row!
        assert analyses_3[0].result.get("summary") == "Third summary of document A"

    def test_ai_analysis_separate_documents_and_patients(self):
        # E. Two DIFFERENT documents for SAME patient create TWO separate document_extraction analyses
        doc_b = Document(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            file_name="lab_report.pdf",
            file_path="uploads/lab_report.pdf",
            document_type="lab_report",
            processing_status="COMPLETED",
            extracted_text="Lab report text",
        )
        self.db.add(doc_b)
        self.db.commit()

        rec_a = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Summary for Doc A",
            confidence_score=0.88,
        )
        rec_b = ExtractedMedicalRecord(
            document_type_detected="lab_report",
            summary="Summary for Doc B",
            confidence_score=0.91,
        )

        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec_a,
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=uuid.UUID(str(doc_b.id)),
            extracted=rec_b,
        )

        patient_analyses = (
            self.db.query(AIAnalysis)
            .filter(
                AIAnalysis.patient_id == self.patient.id,
                AIAnalysis.analysis_type == "document_extraction",
            )
            .all()
        )
        assert len(patient_analyses) == 2  # Doc A -> 1, Doc B -> 1 => Total 2

        # F. Different patients remain isolated
        user_other = User(id=uuid.uuid4(), email="other_patient@example.com")
        patient_other_id = uuid.uuid4()
        doc_other_id = uuid.uuid4()
        patient_other = Patient(id=patient_other_id, user_id=user_other.id)
        doc_other = Document(
            id=doc_other_id,
            patient_id=patient_other_id,
            file_name="other_doc.pdf",
            file_path="uploads/other_doc.pdf",
            document_type="other",
            processing_status="COMPLETED",
        )
        self.db.add_all([user_other, patient_other, doc_other])
        self.db.commit()

        self.service.persist_extracted_record(
            db=self.db,
            patient_id=patient_other_id,
            document_id=doc_other_id,
            extracted=rec_a,
        )

        other_analyses = (
            self.db.query(AIAnalysis)
            .filter(AIAnalysis.patient_id == patient_other_id)
            .all()
        )
        assert len(other_analyses) == 1
        assert other_analyses[0].result.get("document_id") == str(doc_other_id)

    def test_ai_analysis_qa_not_deduplicated(self):
        # G. QA analyses are NOT deduplicated
        qa_analysis_1 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="qa",
            result={"paragraphs": ["Answer 1"]},
            confidence=0.95,
        )
        qa_analysis_2 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="qa",
            result={"paragraphs": ["Answer 2"]},
            confidence=0.95,
        )
        self.db.add_all([qa_analysis_1, qa_analysis_2])
        self.db.commit()

        rec_doc = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Doc summary",
            confidence_score=0.9,
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec_doc,
        )

        all_patient_analyses = (
            self.db.query(AIAnalysis)
            .filter(AIAnalysis.patient_id == self.patient.id)
            .all()
        )
        # 2 QA analyses + 1 document extraction = 3 total AIAnalysis rows
        assert len(all_patient_analyses) == 3

    def test_legacy_ai_analysis_without_document_id_handling(self):
        # Legacy AIAnalysis record without document_id in result dictionary
        legacy_analysis = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="document_extraction",
            result={"summary": "Legacy extraction without document_id", "persisted_counts": {}},
            confidence=0.8,
        )
        self.db.add(legacy_analysis)
        self.db.commit()

        # Re-extract document - should not crash on legacy record, and creates canonical record with document_id
        rec = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="New extraction summary",
            confidence_score=0.9,
        )
        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec,
        )

        all_analyses = (
            self.db.query(AIAnalysis)
            .filter(AIAnalysis.patient_id == self.patient.id)
            .all()
        )
        assert len(all_analyses) == 2

    def test_empty_events_fallback_creation(self):
        # Given: events = [] for consultation_note document
        rec = ExtractedMedicalRecord(
            document_type_detected="consultation_note",
            summary="Patient attended a medical consultation for chronic cough.",
            confidence_score=0.9,
            events=[],
        )

        counts = self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec,
        )

        assert counts["events"] == 1
        events = self.db.query(MedicalEvent).filter(MedicalEvent.patient_id == self.patient.id).all()
        assert len(events) == 1
        assert events[0].document_id == self.document_id
        assert events[0].patient_id == self.patient_id
        assert events[0].event_type == "consultation"
        assert events[0].event_date is None  # NEVER invent clinical date
        assert events[0].title == "Clinical Consultation Encounter"
        assert "Patient attended a medical consultation" in events[0].description

    def test_explicit_events_prevent_fallback_creation(self):
        # Given: events = [explicit_event]
        explicit_ev = ExtractedMedicalEvent(
            event_type="procedure",
            event_date=date(2026, 5, 10),
            title="Colonoscopy Procedure",
            description="Routine screening colonoscopy",
        )
        rec = ExtractedMedicalRecord(
            document_type_detected="consultation_note",
            summary="Procedure note",
            confidence_score=0.95,
            events=[explicit_ev],
        )

        counts = self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec,
        )

        assert counts["events"] == 1
        events = self.db.query(MedicalEvent).filter(MedicalEvent.patient_id == self.patient.id).all()
        assert len(events) == 1
        assert events[0].title == "Colonoscopy Procedure"
        assert events[0].event_date == date(2026, 5, 10)

    def test_fallback_event_reextraction_idempotency(self):
        # Extract twice with events = []
        rec = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Initial Rx summary",
            confidence_score=0.9,
            events=[],
        )

        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec,
        )

        rec_updated = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Updated Rx summary",
            confidence_score=0.95,
            events=[],
        )

        self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec_updated,
        )

        # Should still be exactly 1 MedicalEvent for this document
        events = self.db.query(MedicalEvent).filter(MedicalEvent.patient_id == self.patient.id).all()
        assert len(events) == 1
        assert events[0].description == "Updated Rx summary"

    def test_fallback_event_multiple_documents(self):
        doc2_id = uuid.uuid4()
        doc2 = Document(
            id=doc2_id,
            patient_id=self.patient_id,
            file_name="lab_report.pdf",
            file_path="uploads/lab_report.pdf",
            document_type="lab_report",
            processing_status="COMPLETED",
        )
        self.db.add(doc2)
        self.db.commit()

        rec1 = ExtractedMedicalRecord(
            document_type_detected="prescription",
            summary="Rx 1",
            events=[],
        )
        rec2 = ExtractedMedicalRecord(
            document_type_detected="lab_report",
            summary="Lab Report 2",
            events=[],
        )

        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=self.document_id, extracted=rec1)
        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=doc2_id, extracted=rec2)

        events = self.db.query(MedicalEvent).filter(MedicalEvent.patient_id == self.patient.id).all()
        assert len(events) == 2
        doc_ids = {e.document_id for e in events}
        assert self.document_id in doc_ids
        assert doc2_id in doc_ids

    def test_finding_creation_with_source_document_id(self):
        rec = ExtractedMedicalRecord(
            document_type_detected="consultation_note",
            summary="Patient has elevated temperature.",
            findings=[
                ExtractedFinding(
                    finding_type="symptom",
                    title="High Body Temperature",
                    description="Fever of 38.5C observed",
                    risk_level="high",
                    confidence=0.95,
                    recommendation="Administer antipyretics",
                )
            ],
        )

        counts = self.service.persist_extracted_record(
            db=self.db,
            patient_id=self.patient_id,
            document_id=self.document_id,
            extracted=rec,
        )

        assert counts["findings"] == 1
        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient_id).all()
        assert len(findings) == 1
        assert findings[0].title == "High Body Temperature"
        assert findings[0].source_document_id == self.document_id

    def test_finding_same_document_reextraction_idempotency(self):
        # Extraction #1
        rec1 = ExtractedMedicalRecord(
            document_type_detected="consultation_note",
            summary="Initial assessment",
            findings=[
                ExtractedFinding(
                    finding_type="symptom",
                    title="High Body Temperature",
                    description="Initial fever note",
                    risk_level="medium",
                    confidence=0.8,
                )
            ],
        )
        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=self.document_id, extracted=rec1)

        # Extraction #2 (Re-extraction of Document A with updated values)
        rec2 = ExtractedMedicalRecord(
            document_type_detected="consultation_note",
            summary="Updated assessment",
            findings=[
                ExtractedFinding(
                    finding_type="symptom",
                    title="High Body Temperature",
                    description="Confirmed high fever 39.0C",
                    risk_level="high",
                    confidence=0.95,
                    recommendation="Urgent antipyretic administration",
                )
            ],
        )
        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=self.document_id, extracted=rec2)

        # Must still be exactly 1 Finding row for this document
        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient_id).all()
        assert len(findings) == 1
        assert findings[0].description == "Confirmed high fever 39.0C"
        assert findings[0].risk_level == "high"
        assert findings[0].confidence == 0.95
        assert findings[0].recommendation == "Urgent antipyretic administration"

    def test_finding_different_documents_same_title(self):
        doc2_id = uuid.uuid4()
        doc2 = Document(
            id=doc2_id,
            patient_id=self.patient_id,
            file_name="visit_aug20.pdf",
            file_path="uploads/visit_aug20.pdf",
            document_type="consultation_note",
            processing_status="COMPLETED",
        )
        self.db.add(doc2)
        self.db.commit()

        # Document A finding
        rec1 = ExtractedMedicalRecord(
            summary="Visit Aug 16",
            findings=[ExtractedFinding(title="High Body Temperature", description="Visit 1 fever")],
        )
        # Document B finding (different document, same finding title)
        rec2 = ExtractedMedicalRecord(
            summary="Visit Aug 20",
            findings=[ExtractedFinding(title="High Body Temperature", description="Visit 2 fever")],
        )

        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=self.document_id, extracted=rec1)
        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=doc2_id, extracted=rec2)

        # Must be 2 distinct Finding rows, each associated with their respective source document
        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient_id).all()
        assert len(findings) == 2
        doc_map = {f.source_document_id: f.description for f in findings}
        assert doc_map[self.document_id] == "Visit 1 fever"
        assert doc_map[doc2_id] == "Visit 2 fever"

    def test_finding_same_document_multiple_distinct_findings(self):
        rec = ExtractedMedicalRecord(
            summary="Multi-finding assessment",
            findings=[
                ExtractedFinding(title="High Body Temperature", description="Fever"),
                ExtractedFinding(title="Dengue", description="Positive NS1 antigen"),
                ExtractedFinding(title="Weakness", description="Generalized fatigue"),
            ],
        )

        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=self.document_id, extracted=rec)

        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient_id).all()
        assert len(findings) == 3
        titles = {f.title for f in findings}
        assert titles == {"High Body Temperature", "Dengue", "Weakness"}

    def test_finding_duplicate_entries_in_single_payload(self):
        # Payload containing identical finding titles twice
        rec = ExtractedMedicalRecord(
            summary="Duplicate findings payload",
            findings=[
                ExtractedFinding(title="High Body Temperature", description="First entry"),
                ExtractedFinding(title="High Body Temperature", description="Second entry"),
            ],
        )

        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=self.document_id, extracted=rec)

        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient_id).all()
        assert len(findings) == 1
        assert findings[0].title == "High Body Temperature"

    def test_finding_legacy_null_source_document_id_handling(self):
        # Historical finding row with source_document_id = NULL
        legacy_finding = Finding(
            patient_id=self.patient_id,
            finding_type="diagnosis",
            title="High Body Temperature",
            description="Legacy finding without source_document_id",
            source_document_id=None,
        )
        self.db.add(legacy_finding)
        self.db.commit()

        # Extract document — should create a new finding linked to this document without interfering with legacy row
        rec = ExtractedMedicalRecord(
            summary="New extraction",
            findings=[ExtractedFinding(title="High Body Temperature", description="New finding with document_id")],
        )

        self.service.persist_extracted_record(db=self.db, patient_id=self.patient_id, document_id=self.document_id, extracted=rec)

        findings = self.db.query(Finding).filter(Finding.patient_id == self.patient_id).all()
        assert len(findings) == 2
        null_docs = [f for f in findings if f.source_document_id is None]
        linked_docs = [f for f in findings if f.source_document_id == self.document_id]
        assert len(null_docs) == 1
        assert len(linked_docs) == 1
