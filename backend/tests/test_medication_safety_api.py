import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_application_user
from app.db.database import Base, get_db
from app.main import app
from app.models.allergy import Allergy
from app.models.finding import Finding
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.user import User

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

CHECK_ENDPOINT = "/api/medication-safety/check"
ANALYZE_ENDPOINT = "/api/medication-safety/analyze"


# ----------------------------------------------------------------------
# Fixtures
#
# These follow the dependency_overrides pattern from test_records.py, but back
# get_db with a real SQLite session instead of a MagicMock: the endpoints run a
# multi-step analysis across three tables, and the patient-isolation assertions
# are only meaningful if the filters actually execute.
# ----------------------------------------------------------------------


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def patient_a(db_session):
    return _create_patient(db_session, "patient_a@example.com")


@pytest.fixture
def patient_b(db_session):
    return _create_patient(db_session, "patient_b@example.com")


@pytest.fixture
def client(db_session, patient_a):
    """TestClient authenticated as patient A."""
    user, _ = patient_a
    with _authenticated_client(db_session, user) as test_client:
        yield test_client


class _authenticated_client:
    """
    Installs the auth/db dependency overrides for one user, then clears them.

    app.dependency_overrides is global state on the shared app singleton, so only
    one identity can be installed at a time. Tests that need to act as two
    different users must enter this context twice in sequence, never nest or hold
    two clients at once.
    """

    def __init__(self, session, user):
        self.session = session
        self.user = user

    def __enter__(self):
        def override_get_current_user():
            return self.user

        def override_get_db():
            yield self.session

        app.dependency_overrides[get_current_application_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db

        self._client = TestClient(app)
        return self._client.__enter__()

    def __exit__(self, *exc_info):
        self._client.__exit__(*exc_info)
        app.dependency_overrides.clear()
        return False


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _create_patient(db, email):
    user = User(id=uuid.uuid4(), email=email)
    db.add(user)
    db.commit()
    patient = Patient(id=uuid.uuid4(), user_id=user.id)
    db.add(patient)
    db.commit()
    return user, patient


def _add_medication(db, patient, name, normalized_name, end_date=None, dosage="10mg"):
    medication = Medication(
        id=uuid.uuid4(),
        patient_id=patient.id,
        name=name,
        normalized_name=normalized_name,
    )
    db.add(medication)
    db.commit()

    prescription = Prescription(
        id=uuid.uuid4(),
        patient_id=patient.id,
        medication_id=medication.id,
        dosage=dosage,
        frequency="once daily",
        end_date=end_date,
    )
    db.add(prescription)
    db.commit()
    return medication


def _add_allergy(db, patient, medication_name, normalized_name, severity="severe"):
    allergy = Allergy(
        id=uuid.uuid4(),
        patient_id=patient.id,
        medication_name=medication_name,
        normalized_medication_name=normalized_name,
        reaction="Rash",
        severity=severity,
    )
    db.add(allergy)
    db.commit()
    return allergy


def _seed_interaction(db, patient):
    """Gives the patient an interacting warfarin + aspirin combination."""
    _add_medication(db, patient, "Warfarin 5mg", "warfarin")
    _add_medication(db, patient, "Aspirin 75mg", "aspirin")


# ----------------------------------------------------------------------
# A / B. Authentication
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,endpoint",
    [
        ("get", CHECK_ENDPOINT),
        ("post", ANALYZE_ENDPOINT),
    ],
)
def test_unauthenticated_medication_safety_endpoints_return_401(method, endpoint):
    """
    Security Audit Test:
    Ensures both medication safety endpoints require authentication and reject
    unauthenticated requests with HTTP 401.
    """
    # Use clean app without dependency overrides
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = getattr(unauth_client, method)(endpoint)
        assert response.status_code == 401
        assert "credentials were not provided" in response.json()["detail"].lower() or "unauthorized" in response.json()["detail"].lower() or "scheme" in response.json()["detail"].lower()


def test_invalid_authentication_scheme_is_rejected():
    """
    Security Audit Test:
    A non-Bearer Authorization header is rejected with HTTP 401.
    """
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = unauth_client.get(CHECK_ENDPOINT, headers={"Authorization": "Basic abc123"})
        assert response.status_code == 401


# ----------------------------------------------------------------------
# E / F / G. Detection results
# ----------------------------------------------------------------------


def test_check_returns_known_interaction(client, db_session, patient_a):
    """GET /check reports a known drug interaction for the authenticated patient."""
    _, patient = patient_a
    _seed_interaction(db_session, patient)

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["finding_count"] == 1
    assert data["highest_risk_level"] == "high"
    assert data["active_medication_count"] == 2

    issue = data["issues"][0]
    assert issue["kind"] == "interaction"
    assert issue["finding_type"] == "drug_interaction"
    assert issue["risk_level"] == "high"
    assert issue["id"] == "drug_interaction:aspirin+warfarin"
    assert "bleeding" in issue["description"].lower()
    assert issue["recommendation"]
    assert issue["confidence"] == 0.90
    assert sorted(issue["medications"]) == ["Aspirin 75mg", "Warfarin 5mg"]


def test_check_returns_allergy_contraindication(client, db_session, patient_a):
    """GET /check reports a medication that matches a documented allergy."""
    _, patient = patient_a
    _add_medication(db_session, patient, "Amoxicillin 500mg", "amoxicillin")
    _add_allergy(db_session, patient, "Amoxicillin", "amoxicillin", severity="severe")

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["finding_count"] == 1
    issue = data["issues"][0]
    assert issue["kind"] == "allergy"
    assert issue["finding_type"] == "allergy_contraindication"
    assert issue["risk_level"] == "high"
    assert "Rash" in issue["description"]


def test_check_returns_duplicate_medication(client, db_session, patient_a):
    """GET /check reports duplicate therapy using the shared flag vocabulary."""
    _, patient = patient_a
    _add_medication(db_session, patient, "Warfarin 5mg", "warfarin")
    _add_medication(db_session, patient, "Coumadin (Warfarin)", "warfarin")

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["finding_count"] == 1
    assert data["issues"][0]["kind"] == "duplicate"
    assert data["issues"][0]["risk_level"] == "medium"


def test_check_returns_dosage_issue(client, db_session, patient_a):
    """GET /check reports a dose above its configured ceiling as kind 'dosage'."""
    _, patient = patient_a
    _add_medication(db_session, patient, "Paracetamol 500mg", "paracetamol", dosage="1500mg")

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["finding_count"] == 1
    issue = data["issues"][0]
    assert issue["kind"] == "dosage"
    assert issue["finding_type"] == "dosage_exceeded"
    assert issue["risk_level"] == "high"
    assert issue["id"] == "dosage_exceeded:paracetamol"
    assert "1500mg" in issue["description"]


def test_check_ignores_unparseable_dosage(client, db_session, patient_a):
    """An unreadable dosage string never produces a dosage issue."""
    _, patient = patient_a
    _add_medication(db_session, patient, "Paracetamol 500mg", "paracetamol", dosage="as directed")

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    assert response.json()["finding_count"] == 0


def test_check_returns_no_issues_for_safe_medication_list(client, db_session, patient_a):
    """GET /check reports nothing when the medication list is safe."""
    _, patient = patient_a
    _add_medication(db_session, patient, "Paracetamol 500mg", "paracetamol")

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["finding_count"] == 0
    assert data["issues"] == []
    assert data["highest_risk_level"] is None
    assert data["active_medication_count"] == 1


def test_check_does_not_persist_findings(client, db_session, patient_a):
    """GET /check is read-only and writes no Finding rows."""
    _, patient = patient_a
    _seed_interaction(db_session, patient)

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    assert response.json()["finding_count"] == 1
    assert db_session.query(Finding).count() == 0


# ----------------------------------------------------------------------
# C / D / J. Patient isolation
# ----------------------------------------------------------------------


def test_authenticated_user_sees_only_their_own_safety_data(client, db_session, patient_a, patient_b):
    """
    Security Audit Test:
    The report covers only the authenticated user's patient record.
    """
    _, patient_a_record = patient_a
    _, patient_b_record = patient_b

    # Patient A takes a single safe medication.
    _add_medication(db_session, patient_a_record, "Paracetamol 500mg", "paracetamol")
    # Patient B takes an interacting combination and has an allergy.
    _seed_interaction(db_session, patient_b_record)
    _add_allergy(db_session, patient_b_record, "Penicillin", "penicillin")

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["active_medications"] == ["paracetamol"]
    assert data["finding_count"] == 0


def test_other_patients_medications_never_appear_in_response(db_session, patient_a, patient_b):
    """
    Security Audit Test:
    Neither patient's medications, allergies or issues leak into the other's report.
    """
    user_a, patient_a_record = patient_a
    user_b, patient_b_record = patient_b

    _add_medication(db_session, patient_a_record, "Amoxicillin 500mg", "amoxicillin")
    _add_allergy(db_session, patient_a_record, "Amoxicillin", "amoxicillin")
    _seed_interaction(db_session, patient_b_record)

    with _authenticated_client(db_session, user_a) as client_a:
        response_a = client_a.get(CHECK_ENDPOINT)
    assert response_a.status_code == 200
    data_a = response_a.json()

    assert data_a["active_medications"] == ["amoxicillin"]
    assert [i["kind"] for i in data_a["issues"]] == ["allergy"]
    assert "warfarin" not in str(data_a).lower()
    assert "aspirin" not in str(data_a).lower()

    with _authenticated_client(db_session, user_b) as client_b:
        response_b = client_b.get(CHECK_ENDPOINT)
    assert response_b.status_code == 200
    data_b = response_b.json()

    assert sorted(data_b["active_medications"]) == ["aspirin", "warfarin"]
    assert [i["kind"] for i in data_b["issues"]] == ["interaction"]
    assert "amoxicillin" not in str(data_b).lower()


@pytest.mark.parametrize("endpoint,method", [(CHECK_ENDPOINT, "get"), (ANALYZE_ENDPOINT, "post")])
def test_supplied_patient_id_cannot_access_another_patient(
    client, db_session, patient_a, patient_b, endpoint, method
):
    """
    Security Audit Test:
    A patient_id supplied by the caller is ignored; the report is always resolved
    from the authenticated session.
    """
    _, patient_a_record = patient_a
    _, patient_b_record = patient_b

    _add_medication(db_session, patient_a_record, "Paracetamol 500mg", "paracetamol")
    _seed_interaction(db_session, patient_b_record)

    request = getattr(client, method)
    kwargs = {"params": {"patient_id": str(patient_b_record.id)}}
    if method == "post":
        kwargs["json"] = {"patient_id": str(patient_b_record.id)}

    response = request(endpoint, **kwargs)
    assert response.status_code == 200

    report = response.json() if method == "get" else response.json()["report"]
    assert report["active_medications"] == ["paracetamol"]
    assert report["finding_count"] == 0


def test_analyze_stores_findings_against_the_authenticated_patient_only(
    client, db_session, patient_a, patient_b
):
    """
    Security Audit Test:
    POST /analyze writes findings for the authenticated patient and leaves other
    patients' findings untouched.
    """
    _, patient_a_record = patient_a
    _, patient_b_record = patient_b

    _seed_interaction(db_session, patient_a_record)
    _seed_interaction(db_session, patient_b_record)

    response = client.post(ANALYZE_ENDPOINT)
    assert response.status_code == 200

    findings = db_session.query(Finding).all()
    assert len(findings) == 1
    assert findings[0].patient_id == patient_a_record.id
    assert db_session.query(Finding).filter(Finding.patient_id == patient_b_record.id).count() == 0


# ----------------------------------------------------------------------
# H / I. Persistence
# ----------------------------------------------------------------------


def test_analyze_persists_findings(client, db_session, patient_a):
    """POST /analyze records the detected issues as Finding rows."""
    _, patient = patient_a
    _seed_interaction(db_session, patient)

    response = client.post(ANALYZE_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["persistence"] == {"created": 1, "updated": 0, "unchanged": 0, "removed": 0}
    assert data["report"]["finding_count"] == 1
    assert data["report"]["issues"][0]["kind"] == "interaction"

    findings = db_session.query(Finding).all()
    assert len(findings) == 1
    assert findings[0].finding_type == "drug_interaction"
    assert findings[0].risk_level == "high"
    assert findings[0].title == "Drug interaction: Aspirin + Warfarin"


def test_repeated_analyze_does_not_create_duplicate_findings(client, db_session, patient_a):
    """Repeating POST /analyze keeps exactly one Finding row per issue."""
    _, patient = patient_a
    _seed_interaction(db_session, patient)

    first = client.post(ANALYZE_ENDPOINT)
    second = client.post(ANALYZE_ENDPOINT)
    third = client.post(ANALYZE_ENDPOINT)

    assert first.json()["persistence"]["created"] == 1
    assert second.json()["persistence"] == {"created": 0, "updated": 0, "unchanged": 1, "removed": 0}
    assert third.json()["persistence"]["created"] == 0
    assert db_session.query(Finding).count() == 1


def test_analyze_with_no_issues_creates_nothing(client, db_session, patient_a):
    """POST /analyze writes nothing when the medication list is safe."""
    _, patient = patient_a
    _add_medication(db_session, patient, "Paracetamol 500mg", "paracetamol")

    response = client.post(ANALYZE_ENDPOINT)
    assert response.status_code == 200

    assert response.json()["persistence"]["created"] == 0
    assert db_session.query(Finding).count() == 0


def test_analyze_leaves_unrelated_findings_untouched(client, db_session, patient_a):
    """POST /analyze does not modify findings created by other sources."""
    _, patient = patient_a
    diagnosis = Finding(
        id=uuid.uuid4(),
        patient_id=patient.id,
        finding_type="diagnosis",
        title="Acute Bronchitis",
        description="Infection of the bronchial tree",
        risk_level="medium",
    )
    db_session.add(diagnosis)
    db_session.commit()
    _seed_interaction(db_session, patient)

    response = client.post(ANALYZE_ENDPOINT)
    assert response.status_code == 200

    remaining = {f.finding_type for f in db_session.query(Finding).all()}
    assert remaining == {"diagnosis", "drug_interaction"}


# ----------------------------------------------------------------------
# Response shape
# ----------------------------------------------------------------------


def test_response_does_not_expose_internal_identifiers(client, db_session, patient_a):
    """
    Security Audit Test:
    The response exposes no patient_id, user_id or medication row identifiers.
    """
    user, patient = patient_a
    _seed_interaction(db_session, patient)

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200
    data = response.json()
    body = str(data)

    assert "patient_id" not in body
    assert "user_id" not in body
    assert "medication_ids" not in body
    assert str(patient.id) not in body
    assert str(user.id) not in body
    assert set(data.keys()) == {
        "reference_date",
        "active_medication_count",
        "active_medications",
        "finding_count",
        "highest_risk_level",
        "issues",
    }


def test_issue_schema_fields(client, db_session, patient_a):
    """Each issue exposes exactly the documented public fields."""
    _, patient = patient_a
    _seed_interaction(db_session, patient)

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200

    issue = response.json()["issues"][0]
    assert set(issue.keys()) == {
        "id",
        "kind",
        "finding_type",
        "risk_level",
        "title",
        "medications",
        "description",
        "recommendation",
        "confidence",
    }


def test_issue_kinds_match_frontend_flag_vocabulary(client, db_session, patient_a):
    """
    The kind values are limited to the frontend's MedicationFlagKind vocabulary
    ("interaction", "duplicate", "dosage", "allergy").
    """
    _, patient = patient_a
    _seed_interaction(db_session, patient)
    _add_medication(db_session, patient, "Coumadin (Warfarin)", "warfarin")
    _add_allergy(db_session, patient, "Aspirin", "aspirin")
    _add_medication(db_session, patient, "Paracetamol 500mg", "paracetamol", dosage="1500mg")

    response = client.get(CHECK_ENDPOINT)
    assert response.status_code == 200

    kinds = {i["kind"] for i in response.json()["issues"]}
    assert kinds == {"interaction", "duplicate", "allergy", "dosage"}
    assert kinds <= {"interaction", "duplicate", "dosage", "allergy"}
