import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.document import Document
from app.models.finding import Finding
from app.models.patient import Patient
from app.models.user import User
from app.scripts.clean_duplicate_findings import clean_duplicate_findings

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class CleanDuplicateFindingsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()

        # Seed User & Patient A
        self.user_a = User(id=uuid.uuid4(), email=f"patient_a_{uuid.uuid4().hex[:8]}@example.com")
        self.db.add(self.user_a)
        self.db.commit()

        self.patient_a_id = uuid.uuid4()
        self.patient_a = Patient(id=self.patient_a_id, user_id=self.user_a.id)
        self.db.add(self.patient_a)
        self.db.commit()

        # Seed User & Patient B
        self.user_b = User(id=uuid.uuid4(), email=f"patient_b_{uuid.uuid4().hex[:8]}@example.com")
        self.db.add(self.user_b)
        self.db.commit()

        self.patient_b_id = uuid.uuid4()
        self.patient_b = Patient(id=self.patient_b_id, user_id=self.user_b.id)
        self.db.add(self.patient_b)
        self.db.commit()

        # Seed Document 1 for Patient A
        self.doc_1_id = uuid.uuid4()
        self.doc_1 = Document(
            id=self.doc_1_id,
            patient_id=self.patient_a_id,
            file_name="Doc1.pdf",
            file_path="uploads/Doc1.pdf",
            document_type="consultation_note",
            processing_status="COMPLETED",
        )
        self.db.add(self.doc_1)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(Finding).delete()
        self.db.query(Document).delete()
        self.db.query(Patient).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_safe_legacy_duplicate_detected(self):
        # Current document-linked finding
        doc_linked_finding = Finding(
            patient_id=self.patient_a_id,
            source_document_id=self.doc_1_id,
            finding_type="symptom",
            title="High Body Temperature",
            description="Document linked fever",
        )

        # Legacy NULL-source finding with matching title
        legacy_finding = Finding(
            patient_id=self.patient_a_id,
            source_document_id=None,
            finding_type="symptom",
            title="High Body Temperature",
            description="Legacy fever",
        )
        self.db.add_all([doc_linked_finding, legacy_finding])
        self.db.commit()

        res = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=True)

        assert res["total_inspected"] == 2
        assert res["document_linked_preserved"] == 1
        assert res["legacy_null_total"] == 1
        assert res["safe_candidates"] == 1
        assert res["ambiguous_preserved"] == 0
        assert res["unmapped_preserved"] == 0

        # Check detail formatting
        assert len(res["candidates_details"]) == 1
        detail = res["candidates_details"][0]
        assert detail["legacy_finding_id"] == str(legacy_finding.id)
        assert detail["matching_current_finding_id"] == str(doc_linked_finding.id)
        assert detail["matching_current_source_document_id"] == str(self.doc_1_id)
        assert detail["matching_document_filename"] == "Doc1.pdf"

    def test_dry_run_does_not_delete(self):
        doc_linked = Finding(patient_id=self.patient_a_id, source_document_id=self.doc_1_id, finding_type="symptom", title="Fever", description="Linked")
        legacy = Finding(patient_id=self.patient_a_id, source_document_id=None, finding_type="symptom", title="Fever", description="Legacy")
        self.db.add_all([doc_linked, legacy])
        self.db.commit()

        res = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=True)
        assert res["safe_candidates"] == 1
        assert res["records_deleted"] == 0

        all_findings = self.db.query(Finding).all()
        assert len(all_findings) == 2

    def test_execute_deletes_only_safe_duplicates(self):
        doc_linked = Finding(patient_id=self.patient_a_id, source_document_id=self.doc_1_id, finding_type="symptom", title="Fever", description="Linked")
        legacy = Finding(patient_id=self.patient_a_id, source_document_id=None, finding_type="symptom", title="Fever", description="Legacy")
        self.db.add_all([doc_linked, legacy])
        self.db.commit()

        res = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=False)
        assert res["safe_candidates"] == 1
        assert res["records_deleted"] == 1

        all_findings = self.db.query(Finding).all()
        assert len(all_findings) == 1
        assert all_findings[0].id == doc_linked.id

    def test_current_document_linked_finding_preserved(self):
        doc_linked = Finding(patient_id=self.patient_a_id, source_document_id=self.doc_1_id, finding_type="symptom", title="Fever", description="Linked")
        self.db.add(doc_linked)
        self.db.commit()

        res = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=False)
        assert res["safe_candidates"] == 0
        assert res["records_deleted"] == 0

        remaining = self.db.query(Finding).all()
        assert len(remaining) == 1
        assert remaining[0].id == doc_linked.id

    def test_unmapped_legacy_finding_preserved(self):
        legacy_unmapped = Finding(patient_id=self.patient_a_id, source_document_id=None, finding_type="symptom", title="Rare Finding", description="No document match")
        self.db.add(legacy_unmapped)
        self.db.commit()

        res = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=False)
        assert res["unmapped_preserved"] == 1
        assert res["safe_candidates"] == 0
        assert res["records_deleted"] == 0

        remaining = self.db.query(Finding).all()
        assert len(remaining) == 1
        assert remaining[0].id == legacy_unmapped.id

    def test_ambiguous_legacy_finding_preserved(self):
        # Two separate documents for Patient A
        doc_2_id = uuid.uuid4()
        doc_2 = Document(id=doc_2_id, patient_id=self.patient_a_id, file_name="Doc2.pdf", file_path="uploads/Doc2.pdf", document_type="lab_report")
        self.db.add(doc_2)
        self.db.commit()

        doc_linked_1 = Finding(patient_id=self.patient_a_id, source_document_id=self.doc_1_id, finding_type="symptom", title="Fever", description="Doc 1")
        doc_linked_2 = Finding(patient_id=self.patient_a_id, source_document_id=doc_2_id, finding_type="symptom", title="Fever", description="Doc 2")
        legacy_ambiguous = Finding(patient_id=self.patient_a_id, source_document_id=None, finding_type="symptom", title="Fever", description="Ambiguous legacy")
        self.db.add_all([doc_linked_1, doc_linked_2, legacy_ambiguous])
        self.db.commit()

        res = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=False)
        assert res["ambiguous_preserved"] == 1
        assert res["safe_candidates"] == 0
        assert res["records_deleted"] == 0

        remaining = self.db.query(Finding).all()
        assert len(remaining) == 3

    def test_findings_different_documents_same_title_preserved(self):
        doc_2_id = uuid.uuid4()
        doc_2 = Document(id=doc_2_id, patient_id=self.patient_a_id, file_name="Doc2.pdf", file_path="uploads/Doc2.pdf", document_type="lab_report")
        self.db.add(doc_2)
        self.db.commit()

        doc_linked_1 = Finding(patient_id=self.patient_a_id, source_document_id=self.doc_1_id, finding_type="symptom", title="Fever", description="Doc 1")
        doc_linked_2 = Finding(patient_id=self.patient_a_id, source_document_id=doc_2_id, finding_type="symptom", title="Fever", description="Doc 2")
        self.db.add_all([doc_linked_1, doc_linked_2])
        self.db.commit()

        res = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=False)
        assert res["document_linked_preserved"] == 2
        assert res["safe_candidates"] == 0
        assert res["records_deleted"] == 0

        remaining = self.db.query(Finding).all()
        assert len(remaining) == 2

    def test_tenant_isolation(self):
        # Patient A has document-linked finding
        finding_a = Finding(patient_id=self.patient_a_id, source_document_id=self.doc_1_id, finding_type="symptom", title="Fever", description="Patient A")
        # Patient B has legacy finding with same title
        finding_b = Finding(patient_id=self.patient_b_id, source_document_id=None, finding_type="symptom", title="Fever", description="Patient B")
        self.db.add_all([finding_a, finding_b])
        self.db.commit()

        # Clean Patient B
        res_b = clean_duplicate_findings(db=self.db, patient_id=self.patient_b_id, dry_run=False)
        assert res_b["unmapped_preserved"] == 1
        assert res_b["safe_candidates"] == 0
        assert res_b["records_deleted"] == 0

        # Clean all
        res_all = clean_duplicate_findings(db=self.db, dry_run=False)
        assert res_all["unmapped_preserved"] == 1
        assert res_all["safe_candidates"] == 0

        all_findings = self.db.query(Finding).all()
        assert len(all_findings) == 2

    def test_empty_database_safely_handled(self):
        res = clean_duplicate_findings(db=self.db, dry_run=False)
        assert res["total_inspected"] == 0
        assert res["safe_candidates"] == 0
        assert res["records_deleted"] == 0

    def test_idempotent_rerun(self):
        doc_linked = Finding(patient_id=self.patient_a_id, source_document_id=self.doc_1_id, finding_type="symptom", title="Fever", description="Linked")
        legacy = Finding(patient_id=self.patient_a_id, source_document_id=None, finding_type="symptom", title="Fever", description="Legacy")
        self.db.add_all([doc_linked, legacy])
        self.db.commit()

        # Pass 1: Execute
        res1 = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=False)
        assert res1["records_deleted"] == 1

        # Pass 2: Execute again
        res2 = clean_duplicate_findings(db=self.db, patient_id=self.patient_a_id, dry_run=False)
        assert res2["records_deleted"] == 0
        assert res2["safe_candidates"] == 0

        all_findings = self.db.query(Finding).all()
        assert len(all_findings) == 1
        assert all_findings[0].id == doc_linked.id
