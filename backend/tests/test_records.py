import datetime
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_current_application_user
from app.db.database import get_db
from app.main import app
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


@pytest.fixture
def mock_db_session():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_user_and_patient():
    user_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    user = User(id=user_id, email="patient@example.com")
    patient = Patient(id=patient_id, user_id=user_id)
    return user, patient


@pytest.fixture
def client(mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient

    def override_get_current_user():
        return user

    def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_current_application_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_get_medical_overview_empty(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    mock_query = mock_db_session.query.return_value
    mock_filter = mock_query.filter.return_value

    # First call to resolve patient
    mock_filter.first.return_value = patient
    mock_filter.count.return_value = 0

    mock_order = mock_filter.order_by.return_value
    mock_order.first.return_value = None
    mock_order.all.return_value = []
    mock_order.limit.return_value.all.return_value = []

    mock_options = mock_db_session.query.return_value.options.return_value
    mock_options.filter.return_value.order_by.return_value.all.return_value = []
    mock_options.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    response = client.get("/api/records/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == str(patient.id)
    assert data["total_documents"] == 0
    assert data["total_medications"] == 0
    assert data["active_medications"] == []


def test_get_medications_list(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    med_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    doc = Document(id=doc_id, file_name="prescription.pdf")
    pres = Prescription(
        id=uuid.uuid4(),
        patient_id=patient.id,
        document_id=doc_id,
        medication_id=med_id,
        dosage="500mg",
        frequency="twice daily",
        start_date=datetime.date(2026, 1, 15),
        end_date=None,
        instructions="Take with water",
        document=doc,
    )
    med = Medication(
        id=med_id,
        patient_id=patient.id,
        name="Amoxicillin 500mg",
        normalized_name="amoxicillin",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        prescriptions=[pres],
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_options = mock_db_session.query.return_value.options.return_value
    mock_options.filter.return_value.order_by.return_value.all.return_value = [med]

    response = client.get("/api/records/medications")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Amoxicillin 500mg"
    assert data[0]["dosage"] == "500mg"
    assert data[0]["frequency"] == "twice daily"
    assert data[0]["source_document_name"] == "prescription.pdf"
    assert data[0]["status"] == "active"


def test_get_findings_list(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    finding = Finding(
        id=uuid.uuid4(),
        patient_id=patient.id,
        finding_type="contraindication",
        title="Drug Interaction Warning",
        description="Potential interaction between medications.",
        risk_level="high",
        confidence=0.95,
        recommendation="Consult prescribing physician.",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [finding]

    response = client.get("/api/records/findings")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Drug Interaction Warning"
    assert data[0]["risk_level"] == "high"
    assert data[0]["confidence"] == 0.95


def test_get_timeline_events(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    event = MedicalEvent(
        id=uuid.uuid4(),
        patient_id=patient.id,
        event_type="consultation",
        event_date=datetime.date(2026, 2, 10),
        title="Cardiology Consultation",
        description="Routine follow-up.",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_options = mock_db_session.query.return_value.options.return_value
    mock_options.filter.return_value.order_by.return_value.all.return_value = [event]

    response = client.get("/api/records/timeline")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Cardiology Consultation"
    assert data[0]["event_date"] == "2026-02-10"


def test_get_lab_results(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    lab = LabResult(
        id=uuid.uuid4(),
        patient_id=patient.id,
        test_name="Hemoglobin A1c",
        value="5.6",
        unit="%",
        reference_range="4.0-5.7",
        result_date=datetime.date(2026, 3, 1),
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_options = mock_db_session.query.return_value.options.return_value
    mock_options.filter.return_value.order_by.return_value.all.return_value = [lab]

    response = client.get("/api/records/lab-results")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["test_name"] == "Hemoglobin A1c"
    assert data[0]["value"] == "5.6"
    assert data[0]["unit"] == "%"


def test_get_allergies(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    allergy = Allergy(
        id=uuid.uuid4(),
        patient_id=patient.id,
        medication_name="Penicillin",
        normalized_medication_name="penicillin",
        reaction="Skin rash and hives",
        severity="moderate",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [allergy]

    response = client.get("/api/records/allergies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["medication_name"] == "Penicillin"
    assert data[0]["severity"] == "moderate"


def test_get_analyses(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    analysis = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="document_extraction",
        result={"summary": "Patient presented with upper respiratory infection."},
        confidence=0.92,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [analysis]

    response = client.get("/api/records/analyses")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["analysis_type"] == "document_extraction"
    assert data[0]["confidence"] == 0.92
    assert data[0]["result"]["summary"] == "Patient presented with upper respiratory infection."


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/records/overview",
        "/api/records/medications",
        "/api/records/findings",
        "/api/records/timeline",
        "/api/records/lab-results",
        "/api/records/allergies",
        "/api/records/analyses",
    ],
)
def test_unauthenticated_records_endpoints_return_401(endpoint):
    """
    Security Audit Test:
    Ensures that every records endpoint requires authentication and rejects unauthenticated requests with HTTP 401.
    """
    # Use clean app without dependency overrides
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = unauth_client.get(endpoint)
        assert response.status_code == 401
        assert "credentials were not provided" in response.json()["detail"].lower() or "unauthorized" in response.json()["detail"].lower() or "scheme" in response.json()["detail"].lower()


def test_records_patient_isolation_enforced(client, mock_db_session):
    """
    Security Audit Test:
    Ensures that the records endpoints filter strictly by the authenticated patient's ID
    and never leak records belonging to another patient.
    """
    user_a_id = uuid.uuid4()
    patient_a_id = uuid.uuid4()
    user_a = User(id=user_a_id, email="user_a@example.com")
    patient_a = Patient(id=patient_a_id, user_id=user_a_id)

    # Set mock db to resolve patient_a
    mock_db_session.query.return_value.filter.return_value.first.return_value = patient_a

    # Allergy for patient A vs allergy for patient B
    allergy_a = Allergy(
        id=uuid.uuid4(),
        patient_id=patient_a_id,
        medication_name="Amoxicillin",
        severity="high",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [allergy_a]

    response = client.get("/api/records/allergies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["medication_name"] == "Amoxicillin"


def test_timeline_dated_and_undated_events_filtering(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    doc = Document(id=uuid.uuid4(), file_name="consultation.pdf")
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    ev1 = MedicalEvent(
        id=uuid.uuid4(),
        patient_id=patient.id,
        event_type="consultation",
        event_date=datetime.date(2026, 8, 1),
        title="Dated Consultation",
        description="Dated visit description",
        document=doc,
        created_at=now_dt,
    )
    ev2 = MedicalEvent(
        id=uuid.uuid4(),
        patient_id=patient.id,
        event_type="consultation",
        event_date=None,
        title="Undated Consultation",
        description="Undated visit description",
        document=doc,
        created_at=now_dt,
    )

    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_db_session.query.return_value.options.return_value.filter.return_value.order_by.return_value.all.return_value = [ev1, ev2]

    response = client.get("/api/records/timeline")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Dated Consultation"
    assert data[0]["event_date"] == "2026-08-01"
    assert data[1]["title"] == "Undated Consultation"
    assert data[1]["event_date"] is None


def test_get_patient_analyses_deduplication_and_qa_isolation(client, mock_db_session, mock_user_and_patient):
    user, patient = mock_user_and_patient
    doc1_id = str(uuid.uuid4())
    doc2_id = str(uuid.uuid4())

    now = datetime.datetime.now(datetime.timezone.utc)
    old_time = now - datetime.timedelta(hours=2)

    # Document 1 - Old extraction
    a1 = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="document_extraction",
        result={"document_id": doc1_id, "summary": "Old Summary Doc 1"},
        confidence=0.8,
        created_at=old_time,
    )
    # Document 1 - Newer extraction (Duplicate)
    a2 = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="document_extraction",
        result={"document_id": doc1_id, "summary": "New Summary Doc 1"},
        confidence=0.9,
        created_at=now,
    )

    # Document 2 - Extraction
    b1 = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="document_extraction",
        result={"document_id": doc2_id, "summary": "Summary Doc 2"},
        confidence=0.95,
        created_at=now,
    )

    # Legacy Record (No document_id in result)
    legacy = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="document_extraction",
        result={"summary": "Legacy extraction without doc_id"},
        confidence=0.75,
        created_at=old_time,
    )

    # QA Records (3 distinct QA queries)
    qa1 = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="qa",
        result={"paragraphs": ["Answer 1"]},
        confidence=0.9,
        created_at=now,
    )
    qa2 = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="qa",
        result={"paragraphs": ["Answer 2"]},
        confidence=0.9,
        created_at=now,
    )
    qa3 = AIAnalysis(
        id=uuid.uuid4(),
        patient_id=patient.id,
        analysis_type="qa",
        result={"paragraphs": ["Answer 3"]},
        confidence=0.9,
        created_at=now,
    )

    # Query returns records sorted newest first
    mock_db_session.query.return_value.filter.return_value.first.return_value = patient
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        a2, b1, qa1, qa2, qa3, a1, legacy
    ]

    response = client.get("/api/records/analyses")
    assert response.status_code == 200
    data = response.json()

    # Total returned: a2 (Doc 1 latest), b1 (Doc 2), legacy (unmapped), qa1, qa2, qa3 = 6 total (a1 is hidden)
    assert len(data) == 6

    # Verify a1 (older duplicate of Doc 1) was omitted while a2 (newer) was kept
    summaries = [d["result"]["summary"] for d in data if d["analysis_type"] == "document_extraction" and "summary" in d["result"]]
    assert "New Summary Doc 1" in summaries
    assert "Old Summary Doc 1" not in summaries
    assert "Summary Doc 2" in summaries
    assert "Legacy extraction without doc_id" in summaries

    # Verify ALL 3 QA records were kept without deduplication
    qa_records = [d for d in data if d["analysis_type"] == "qa"]
    assert len(qa_records) == 3
