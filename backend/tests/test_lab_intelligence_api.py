import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  - registers every table on Base.metadata
from app.core.security import get_current_application_user
from app.db.database import Base, get_db
from app.main import app
from app.models.document import Document
from app.models.lab_result import LabResult
from app.models.patient import Patient
from app.models.user import User

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

OVERVIEW_ENDPOINT = "/api/lab-intelligence/overview"
TRENDS_ENDPOINT = "/api/lab-intelligence/trends"


def trend_endpoint(test_name: str) -> str:
    return f"/api/lab-intelligence/trends/{test_name}"


# ----------------------------------------------------------------------
# Fixtures
#
# These follow the dependency_overrides pattern from test_medication_safety_api.py,
# backing get_db with a real SQLite session: the endpoints filter on patient_id,
# and the isolation assertions are only meaningful if those filters execute.
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


def _add_document(db, patient, file_name="lab-report.pdf"):
    document = Document(
        id=uuid.uuid4(),
        patient_id=patient.id,
        file_name=file_name,
        file_path=f"private/{patient.id}/{file_name}",
        document_type="lab_report",
        processing_status="completed",
    )
    db.add(document)
    db.commit()
    return document


def _add_lab_result(
    db,
    patient,
    test_name="Glucose",
    value="5.0",
    unit="mg/dL",
    reference_range="3.5 - 5.5",
    result_date=None,
    document=None,
):
    lab_result = LabResult(
        id=uuid.uuid4(),
        patient_id=patient.id,
        document_id=document.id if document else None,
        test_name=test_name,
        value=value,
        unit=unit,
        reference_range=reference_range,
        result_date=result_date,
    )
    db.add(lab_result)
    db.commit()
    return lab_result


# ----------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        OVERVIEW_ENDPOINT,
        TRENDS_ENDPOINT,
        "/api/lab-intelligence/trends/Glucose",
    ],
)
def test_unauthenticated_lab_intelligence_endpoints_return_401(endpoint):
    """
    Security Audit Test:
    Every lab intelligence endpoint requires authentication and rejects
    unauthenticated requests with HTTP 401.
    """
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = unauth_client.get(endpoint)
        assert response.status_code == 401


def test_invalid_authentication_scheme_is_rejected():
    """
    Security Audit Test:
    A non-Bearer Authorization header is rejected with HTTP 401.
    """
    app.dependency_overrides.clear()
    with TestClient(app) as unauth_client:
        response = unauth_client.get(
            OVERVIEW_ENDPOINT,
            headers={"Authorization": "Basic abc123"},
        )
        assert response.status_code == 401


# ----------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------


def test_overview_returns_analysed_results(client, db_session, patient_a):
    """GET /overview returns each result with its classification."""
    _, patient = patient_a
    _add_lab_result(db_session, patient, value="5.0", result_date=date(2026, 1, 1))

    response = client.get(OVERVIEW_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["available_tests"] == ["Glucose"]
    assert len(data["results"]) == 1

    result = data["results"][0]
    assert result["test_name"] == "Glucose"
    assert result["value"] == "5.0"
    assert result["numeric_value"] == 5.0
    assert result["unit"] == "mg/dL"
    assert result["reference_range"] == "3.5 - 5.5"
    assert result["result_date"] == "2026-01-01"
    assert result["status"] == "NORMAL"
    # id is a UUID and must serialise rather than raise a validation error.
    assert uuid.UUID(result["id"])


def test_overview_returns_all_statuses(client, db_session, patient_a):
    """HIGH, LOW, NORMAL and UNKNOWN are all reported correctly."""
    _, patient = patient_a
    _add_lab_result(db_session, patient, test_name="LowTest", value="3.0")
    _add_lab_result(db_session, patient, test_name="NormalTest", value="5.0")
    _add_lab_result(db_session, patient, test_name="HighTest", value="6.0")
    _add_lab_result(db_session, patient, test_name="MalformedValue", value="n/a")
    _add_lab_result(db_session, patient, test_name="CensoredValue", value="<0.01")
    _add_lab_result(
        db_session, patient, test_name="MalformedRange",
        value="5.0", reference_range="not available",
    )

    response = client.get(OVERVIEW_ENDPOINT)
    assert response.status_code == 200

    by_name = {r["test_name"]: r for r in response.json()["results"]}

    assert by_name["LowTest"]["status"] == "LOW"
    assert by_name["NormalTest"]["status"] == "NORMAL"
    assert by_name["HighTest"]["status"] == "HIGH"
    assert by_name["MalformedValue"]["status"] == "UNKNOWN"
    assert by_name["MalformedRange"]["status"] == "UNKNOWN"

    # A censored value keeps its reported text but must not be given a number.
    censored = by_name["CensoredValue"]
    assert censored["value"] == "<0.01"
    assert censored["numeric_value"] is None
    assert censored["status"] == "UNKNOWN"


def test_overview_orders_dated_results_first(client, db_session, patient_a):
    """Dated results are newest first; undated results come last."""
    _, patient = patient_a
    _add_lab_result(db_session, patient, test_name="Undated", result_date=None)
    _add_lab_result(db_session, patient, test_name="Older", result_date=date(2026, 1, 1))
    _add_lab_result(db_session, patient, test_name="Newer", result_date=date(2026, 6, 1))

    response = client.get(OVERVIEW_ENDPOINT)
    assert response.status_code == 200

    names = [r["test_name"] for r in response.json()["results"]]
    assert names == ["Newer", "Older", "Undated"]


def test_overview_with_no_lab_results_returns_empty_payload(client):
    """A patient with no laboratory data gets a valid, empty 200 response."""
    response = client.get(OVERVIEW_ENDPOINT)
    assert response.status_code == 200
    assert response.json() == {"results": [], "available_tests": []}


def test_overview_returns_multiple_tests(client, db_session, patient_a):
    _, patient = patient_a
    _add_lab_result(db_session, patient, test_name="Sodium")
    _add_lab_result(db_session, patient, test_name="Glucose")
    _add_lab_result(db_session, patient, test_name="Potassium")

    response = client.get(OVERVIEW_ENDPOINT)
    assert response.status_code == 200
    data = response.json()

    assert data["available_tests"] == ["Glucose", "Potassium", "Sodium"]
    assert len(data["results"]) == 3


# ----------------------------------------------------------------------
# All trends
# ----------------------------------------------------------------------


def test_trends_returns_one_entry_per_test(client, db_session, patient_a):
    _, patient = patient_a
    _add_lab_result(
        db_session, patient, test_name="Glucose", value="4.0",
        result_date=date(2026, 1, 1),
    )
    _add_lab_result(
        db_session, patient, test_name="Glucose", value="6.0",
        result_date=date(2026, 2, 1),
    )
    _add_lab_result(
        db_session, patient, test_name="Sodium", result_date=date(2026, 1, 1)
    )

    response = client.get(TRENDS_ENDPOINT)
    assert response.status_code == 200
    trends = response.json()["trends"]

    assert [t["test_name"] for t in trends] == ["Glucose", "Sodium"]
    assert trends[0]["trend"] == "INCREASING"
    assert trends[0]["unit"] == "mg/dL"
    assert [p["numeric_value"] for p in trends[0]["points"]] == [4.0, 6.0]
    assert trends[1]["trend"] == "INSUFFICIENT_DATA"


def test_trends_reports_every_direction(client, db_session, patient_a):
    """INCREASING, DECREASING, STABLE and INSUFFICIENT_DATA are all reported."""
    _, patient = patient_a
    for name, values in {
        "Up": ["4.0", "6.0"],
        "Down": ["6.0", "4.0"],
        "Flat": ["5.0", "5.1"],
        "Single": ["5.0"],
    }.items():
        for index, value in enumerate(values):
            _add_lab_result(
                db_session, patient, test_name=name, value=value,
                result_date=date(2026, index + 1, 1),
            )

    response = client.get(TRENDS_ENDPOINT)
    assert response.status_code == 200

    by_name = {t["test_name"]: t["trend"] for t in response.json()["trends"]}

    assert by_name["Up"] == "INCREASING"
    assert by_name["Down"] == "DECREASING"
    assert by_name["Flat"] == "STABLE"
    assert by_name["Single"] == "INSUFFICIENT_DATA"


def test_trends_with_no_lab_results_returns_empty_payload(client):
    response = client.get(TRENDS_ENDPOINT)
    assert response.status_code == 200
    assert response.json() == {"trends": []}


# ----------------------------------------------------------------------
# Single test trend
# ----------------------------------------------------------------------


def test_specific_test_trend_succeeds(client, db_session, patient_a):
    _, patient = patient_a
    _add_lab_result(db_session, patient, value="6.0", result_date=date(2026, 1, 1))
    _add_lab_result(db_session, patient, value="4.0", result_date=date(2026, 2, 1))

    response = client.get(trend_endpoint("Glucose"))
    assert response.status_code == 200
    data = response.json()

    assert data["test_name"] == "Glucose"
    assert data["unit"] == "mg/dL"
    assert data["trend"] == "DECREASING"
    assert [p["numeric_value"] for p in data["points"]] == [6.0, 4.0]
    assert data["points"][0]["result_date"] == "2026-01-01"
    assert data["points"][0]["status"] == "HIGH"


def test_specific_test_trend_matches_case_insensitively(client, db_session, patient_a):
    _, patient = patient_a
    _add_lab_result(db_session, patient, test_name="Glucose")

    response = client.get(trend_endpoint("gLuCoSe"))
    assert response.status_code == 200
    assert response.json()["test_name"] == "Glucose"


def test_nonexistent_test_returns_404(client, db_session, patient_a):
    _, patient = patient_a
    _add_lab_result(db_session, patient, test_name="Glucose")

    response = client.get(trend_endpoint("Sodium"))
    assert response.status_code == 404


def test_specific_test_trend_with_no_lab_results_returns_404(client):
    response = client.get(trend_endpoint("Glucose"))
    assert response.status_code == 404


# ----------------------------------------------------------------------
# Source document fields
# ----------------------------------------------------------------------


def test_overview_exposes_source_document(client, db_session, patient_a):
    """A result extracted from a document reports that document's id and name."""
    _, patient = patient_a
    document = _add_document(db_session, patient, file_name="bloods-jan.pdf")
    _add_lab_result(db_session, patient, document=document)

    response = client.get(OVERVIEW_ENDPOINT)
    assert response.status_code == 200

    result = response.json()["results"][0]
    assert result["source_document_id"] == str(document.id)
    assert result["source_document_name"] == "bloods-jan.pdf"


def test_overview_document_fields_are_null_without_a_document(
    client, db_session, patient_a
):
    """A result with no source document reports nulls, not an error."""
    _, patient = patient_a
    _add_lab_result(db_session, patient, document=None)

    response = client.get(OVERVIEW_ENDPOINT)
    assert response.status_code == 200

    result = response.json()["results"][0]
    assert result["source_document_id"] is None
    assert result["source_document_name"] is None


def test_trend_points_expose_source_document(client, db_session, patient_a):
    _, patient = patient_a
    document = _add_document(db_session, patient, file_name="bloods-feb.pdf")
    _add_lab_result(
        db_session, patient, value="4.0", result_date=date(2026, 1, 1),
        document=document,
    )
    _add_lab_result(
        db_session, patient, value="6.0", result_date=date(2026, 2, 1),
        document=None,
    )

    response = client.get(trend_endpoint("Glucose"))
    assert response.status_code == 200

    points = response.json()["points"]
    assert points[0]["source_document_id"] == str(document.id)
    assert points[0]["source_document_name"] == "bloods-feb.pdf"
    assert points[1]["source_document_id"] is None
    assert points[1]["source_document_name"] is None


@pytest.mark.parametrize(
    "endpoint",
    [OVERVIEW_ENDPOINT, TRENDS_ENDPOINT, "/api/lab-intelligence/trends/Glucose"],
)
def test_internal_storage_path_is_never_exposed(
    endpoint, client, db_session, patient_a
):
    """
    Security Audit Test:
    Document.file_path is internal storage location. No lab intelligence
    response may leak it, on any endpoint.
    """
    _, patient = patient_a
    document = _add_document(db_session, patient)
    _add_lab_result(db_session, patient, document=document)

    response = client.get(endpoint)
    assert response.status_code == 200

    body = response.text
    assert document.file_path not in body
    assert "file_path" not in body
    assert "private/" not in body


def test_all_trends_does_not_issue_a_query_per_test(client, db_session, patient_a):
    """
    /trends must not scale its query count with the number of tests. Ten tests
    are served by a constant number of statements, not one lookup per test.
    """
    _, patient = patient_a
    document = _add_document(db_session, patient)
    for index in range(10):
        _add_lab_result(
            db_session, patient, test_name=f"Test{index:02d}", document=document
        )

    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(test_engine, "before_cursor_execute", record)
    try:
        response = client.get(TRENDS_ENDPOINT)
    finally:
        event.remove(test_engine, "before_cursor_execute", record)

    assert response.status_code == 200
    assert len(response.json()["trends"]) == 10

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 3, f"expected a constant query count, got {len(selects)}"


# ----------------------------------------------------------------------
# Patient isolation
# ----------------------------------------------------------------------


def test_overview_never_returns_another_patients_results(
    db_session, patient_a, patient_b
):
    """
    Security Audit Test:
    Patient A's overview contains only patient A's laboratory data.
    """
    user_a, patient_a_record = patient_a
    _, patient_b_record = patient_b

    _add_lab_result(db_session, patient_a_record, test_name="A-Glucose")
    _add_lab_result(db_session, patient_b_record, test_name="B-Sodium")

    with _authenticated_client(db_session, user_a) as client_a:
        response = client_a.get(OVERVIEW_ENDPOINT)

    assert response.status_code == 200
    data = response.json()

    assert [r["test_name"] for r in data["results"]] == ["A-Glucose"]
    assert data["available_tests"] == ["A-Glucose"]


def test_trends_never_return_another_patients_results(
    db_session, patient_a, patient_b
):
    """
    Security Audit Test:
    Patient A's trend list contains only patient A's tests.
    """
    user_a, patient_a_record = patient_a
    _, patient_b_record = patient_b

    _add_lab_result(db_session, patient_a_record, test_name="A-Glucose")
    _add_lab_result(db_session, patient_b_record, test_name="B-Sodium")

    with _authenticated_client(db_session, user_a) as client_a:
        response = client_a.get(TRENDS_ENDPOINT)

    assert response.status_code == 200
    assert [t["test_name"] for t in response.json()["trends"]] == ["A-Glucose"]


def test_shared_test_name_does_not_expose_another_patients_values(
    db_session, patient_a, patient_b
):
    """
    Security Audit Test:
    Patient B holding results under a test name must not make that test
    reachable for patient A. The lookup returns 404, not patient B's values.
    """
    user_a, _ = patient_a
    _, patient_b_record = patient_b

    _add_lab_result(
        db_session, patient_b_record, test_name="Glucose", value="9.0",
        result_date=date(2026, 1, 1),
    )
    _add_lab_result(
        db_session, patient_b_record, test_name="Glucose", value="12.0",
        result_date=date(2026, 2, 1),
    )

    with _authenticated_client(db_session, user_a) as client_a:
        response = client_a.get(trend_endpoint("Glucose"))

    assert response.status_code == 404
    assert "9.0" not in response.text
    assert "12.0" not in response.text


def test_each_patient_sees_only_their_own_values_for_a_shared_test(
    db_session, patient_a, patient_b
):
    """
    Security Audit Test:
    Both patients record "Glucose"; each trend must contain only its owner's
    values. Asserted in sequence because only one identity can be installed on
    app.dependency_overrides at a time.
    """
    user_a, patient_a_record = patient_a
    user_b, patient_b_record = patient_b

    _add_lab_result(
        db_session, patient_a_record, test_name="Glucose", value="4.0",
        result_date=date(2026, 1, 1),
    )
    _add_lab_result(
        db_session, patient_b_record, test_name="Glucose", value="9.0",
        result_date=date(2026, 1, 1),
    )

    with _authenticated_client(db_session, user_a) as client_a:
        response_a = client_a.get(trend_endpoint("Glucose"))

    with _authenticated_client(db_session, user_b) as client_b:
        response_b = client_b.get(trend_endpoint("Glucose"))

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert [p["numeric_value"] for p in response_a.json()["points"]] == [4.0]
    assert [p["numeric_value"] for p in response_b.json()["points"]] == [9.0]
