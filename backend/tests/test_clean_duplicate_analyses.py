import datetime
import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.ai_analysis import AIAnalysis
from app.models.document import Document
from app.models.patient import Patient
from app.models.user import User
from app.scripts.clean_duplicate_analyses import clean_duplicate_ai_analyses

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class CleanDuplicateAnalysesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

    def setUp(self):
        self.db = TestSessionLocal()

        self.user = User(id=uuid.uuid4(), email="user_clean@example.com")
        self.patient = Patient(id=uuid.uuid4(), user_id=self.user.id)
        self.doc_1 = Document(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            file_name="doc_1.pdf",
            file_path="uploads/doc_1.pdf",
            document_type="prescription",
            processing_status="COMPLETED",
        )
        self.doc_2 = Document(
            id=uuid.uuid4(),
            patient_id=self.patient.id,
            file_name="doc_2.pdf",
            file_path="uploads/doc_2.pdf",
            document_type="lab_report",
            processing_status="COMPLETED",
        )
        self.db.add_all([self.user, self.patient, self.doc_1, self.doc_2])
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(AIAnalysis).delete()
        self.db.query(Document).delete()
        self.db.query(Patient).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()

    def test_dry_run_identifies_duplicates_without_deleting(self):
        # Create 3 duplicate document_extraction records for Doc 1
        now = datetime.datetime.now(datetime.timezone.utc)
        a1 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="document_extraction",
            result={"document_id": str(self.doc_1.id), "summary": "Old summary 1"},
            confidence=0.8,
            created_at=now - datetime.timedelta(hours=2),
        )
        a2 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="document_extraction",
            result={"document_id": str(self.doc_1.id), "summary": "Old summary 2"},
            confidence=0.85,
            created_at=now - datetime.timedelta(hours=1),
        )
        a3 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="document_extraction",
            result={"document_id": str(self.doc_1.id), "summary": "Latest summary"},
            confidence=0.9,
            created_at=now,
        )
        self.db.add_all([a1, a2, a3])
        self.db.commit()

        # Run in dry_run mode
        res = clean_duplicate_ai_analyses(db=self.db, patient_id=self.patient.id, dry_run=True)
        assert res["dry_run"] is True
        assert res["total_scanned"] == 3
        assert res["duplicates_identified"] == 2
        assert res["records_deleted"] == 0

        # DB should still contain all 3 records
        total_in_db = self.db.query(AIAnalysis).count()
        assert total_in_db == 3

    def test_execute_cleanup_deletes_duplicates_keeps_latest(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        a1 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="document_extraction",
            result={"document_id": str(self.doc_1.id), "summary": "Old summary 1"},
            confidence=0.8,
            created_at=now - datetime.timedelta(hours=2),
        )
        a2 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="document_extraction",
            result={"document_id": str(self.doc_1.id), "summary": "Latest summary for Doc 1"},
            confidence=0.9,
            created_at=now,
        )

        # Record for Doc 2
        b1 = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="document_extraction",
            result={"document_id": str(self.doc_2.id), "summary": "Summary for Doc 2"},
            confidence=0.92,
            created_at=now,
        )

        # QA record (must NOT be touched)
        qa = AIAnalysis(
            patient_id=self.patient.id,
            analysis_type="qa",
            result={"paragraphs": ["QA answer"]},
            confidence=0.95,
        )

        self.db.add_all([a1, a2, b1, qa])
        self.db.commit()

        res = clean_duplicate_ai_analyses(db=self.db, patient_id=self.patient.id, dry_run=False)
        assert res["dry_run"] is False
        assert res["records_deleted"] == 1

        # Check DB state
        remaining = self.db.query(AIAnalysis).all()
        assert len(remaining) == 3  # a2 (Doc 1 latest), b1 (Doc 2), and qa

        remaining_doc1 = (
            self.db.query(AIAnalysis)
            .filter(
                AIAnalysis.patient_id == self.patient.id,
                AIAnalysis.analysis_type == "document_extraction",
            )
            .all()
        )
        assert len(remaining_doc1) == 2  # Doc 1 + Doc 2
        doc1_record = [r for r in remaining_doc1 if r.result.get("document_id") == str(self.doc_1.id)][0]
        assert doc1_record.result.get("summary") == "Latest summary for Doc 1"

        # Verify QA record exists
        qa_records = self.db.query(AIAnalysis).filter(AIAnalysis.analysis_type == "qa").all()
        assert len(qa_records) == 1
