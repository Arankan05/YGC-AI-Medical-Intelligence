"""
Tests for the doctor-search API.

Follows the dependency_overrides pattern from test_lab_intelligence_api.py,
backing get_db with a real SQLite session: the endpoints filter on patient_id,
and the isolation assertions are only meaningful if those filters execute.

The two services that reach the public internet are overridden with fakes, so
no test here opens a socket.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  - registers every table on Base.metadata
from app.api.doctor_search import get_directory, get_geocoder
from app.core.security import get_current_application_user
from app.db.database import Base, get_db
from app.main import app
from app.models.finding import Finding
from app.models.patient import Patient
from app.models.user import User
from app.services.geocoding_service import GeocodedLocation
from app.services.provider_directory_errors import (
    GeocodingUnavailableError,
    LocationNotFoundError,
    ProviderLookupUnavailableError,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

SEARCH_ENDPOINT = "/api/doctor-search/search"
HISTORY_ENDPOINT = "/api/doctor-search/history"


def search_endpoint(search_id) -> str:
    return f"/api/doctor-search/searches/{search_id}"


JAFFNA = GeocodedLocation(
    query="Jaffna",
    display_name="Jaffna, Northern Province, Sri Lanka",
    latitude=9.6615,
    longitude=80.0255,
    candidate_count=1,
)

HOSPITAL = {
    "type": "node",
    "id": 1,
    "lat": 9.6698,
    "lon": 80.0206,
    "tags": {
        "amenity": "hospital",
        "name": "Jaffna Teaching Hospital",
        "phone": "+94 21 222 3348",
        "opening_hours": "24/7",
        "addr:street": "Hospital Road",
        "addr:city": "Jaffna",
    },
}

PHARMACY = {
    "type": "node",
    "id": 2,
    "lat": 9.6634,
    "lon": 80.0136,
    "tags": {"amenity": "pharmacy", "name": "Green Cross Pharmacy"},
}


# ----------------------------------------------------------------------
# Fakes for the two services that reach the internet
# ----------------------------------------------------------------------


class FakeGeocoder:
    def __init__(self, result=JAFFNA, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def geocode(self, location, **kwargs):
        self.calls.append(location)
        if self.error is not None:
            raise self.error
        return self.result


class FakeDirectory:
    def __init__(self, elements=None, error=None):
        self.payload = {"elements": list(elements or [])}
        self.error = error
        self.calls = []

    def fetch_healthcare_facilities(self, latitude, longitude, radius_km, kinds=None, **kwargs):
        self.calls.append(
            {"latitude": latitude, "longitude": longitude, "radius_km": radius_km, "kinds": kinds}
        )
        if self.error is not None:
            raise self.error
        return self.payload


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def _create_patient(db, email):
    user = User(id=uuid.uuid4(), email=email)
    db.add(user)
    db.commit()
    patient = Patient(id=uuid.uuid4(), user_id=user.id)
    db.add(patient)
    db.commit()
    return user, patient


@pytest.fixture
def patient_a(db_session):
    return _create_patient(db_session, "patient_a@example.com")


@pytest.fixture
def patient_b(db_session):
    return _create_patient(db_session, "patient_b@example.com")


class _authenticated_client:
    """
    Installs the auth, db and external-service overrides for one user.

    app.dependency_overrides is global state on the shared app singleton, so
    only one identity can be installed at a time. Tests acting as two users must
    enter this context twice in sequence, never nested.
    """

    def __init__(self, session, user, geocoder=None, directory=None):
        self.session = session
        self.user = user
        self.geocoder = geocoder or FakeGeocoder()
        self.directory = directory or FakeDirectory([HOSPITAL])

    def __enter__(self):
        session = self.session

        # Must be a generator function: FastAPI treats a plain callable's return
        # value as the dependency itself rather than yielding from it.
        def override_get_db():
            yield session

        app.dependency_overrides[get_current_application_user] = lambda: self.user
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_geocoder] = lambda: self.geocoder
        app.dependency_overrides[get_directory] = lambda: self.directory

        self._client = TestClient(app)
        return self._client.__enter__()

    def __exit__(self, *exc_info):
        self._client.__exit__(*exc_info)
        app.dependency_overrides.clear()
        return False


@pytest.fixture
def client(db_session, patient_a):
    user, _ = patient_a
    with _authenticated_client(db_session, user) as test_client:
        yield test_client


def post_search(client, **overrides):
    body = {"location": "Jaffna", "radius_km": 10}
    body.update(overrides)
    return client.post(SEARCH_ENDPOINT, json=body)


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------


def test_search_returns_ranked_providers(client):
    response = post_search(client)

    assert response.status_code == 201
    body = response.json()
    assert body["search"]["location_query"] == "Jaffna"
    assert body["search"]["result_count"] == 1
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["provider_name"] == "Jaffna Teaching Hospital"


def test_response_carries_computed_scores(client):
    body = post_search(client).json()
    provider = body["recommendations"][0]

    assert 0 <= provider["match_score"] <= 100
    breakdown = provider["match_breakdown"]
    total = sum(breakdown[k] for k in ("specialty", "distance", "completeness", "verified"))
    assert total == pytest.approx(provider["match_score"])


def test_source_details_are_passed_through(client):
    provider = post_search(client).json()["recommendations"][0]

    assert provider["phone"] == "+94 21 222 3348"
    assert provider["opening_hours"] == "24/7"
    assert provider["address"] == "Hospital Road, Jaffna"
    assert provider["source"] == "openstreetmap"
    assert provider["kind"] == "hospital"


def test_unpublished_details_are_null_not_invented(db_session, patient_a):
    user, _ = patient_a
    with _authenticated_client(db_session, user, directory=FakeDirectory([PHARMACY])) as client:
        body = post_search(client, kinds=["pharmacy"]).json()

    provider = body["recommendations"][0]
    assert provider["phone"] is None
    assert provider["website"] is None
    assert provider["opening_hours"] is None
    assert provider["address"] is None


def test_results_are_ordered_best_first(db_session, patient_a):
    user, _ = patient_a
    directory = FakeDirectory([PHARMACY, HOSPITAL])
    with _authenticated_client(db_session, user, directory=directory) as client:
        body = post_search(client).json()

    scores = [r["match_score"] for r in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)
    assert body["recommendations"][0]["provider_name"] == "Jaffna Teaching Hospital"


def test_radius_is_forwarded_to_the_directory(db_session, patient_a):
    user, _ = patient_a
    directory = FakeDirectory([HOSPITAL])
    with _authenticated_client(db_session, user, directory=directory) as client:
        post_search(client, radius_km=25)

    assert directory.calls[0]["radius_km"] == 25
    assert directory.calls[0]["latitude"] == pytest.approx(JAFFNA.latitude)


# ----------------------------------------------------------------------
# Empty results are a real answer, not an error
# ----------------------------------------------------------------------


def test_no_providers_found_is_a_successful_empty_result(db_session, patient_a):
    user, _ = patient_a
    with _authenticated_client(db_session, user, directory=FakeDirectory([])) as client:
        response = post_search(client)

    assert response.status_code == 201
    body = response.json()
    assert body["recommendations"] == []
    assert body["search"]["result_count"] == 0


def test_an_empty_search_is_still_recorded_in_history(db_session, patient_a):
    user, _ = patient_a
    with _authenticated_client(db_session, user, directory=FakeDirectory([])) as client:
        post_search(client)
        history = client.get(HISTORY_ENDPOINT).json()

    assert len(history["searches"]) == 1
    assert history["searches"][0]["result_count"] == 0


# ----------------------------------------------------------------------
# Upstream failures
# ----------------------------------------------------------------------


def test_unknown_location_is_reported_as_not_found(db_session, patient_a):
    user, _ = patient_a
    geocoder = FakeGeocoder(error=LocationNotFoundError("Atlantis"))
    with _authenticated_client(db_session, user, geocoder=geocoder) as client:
        response = post_search(client, location="Atlantis")

    assert response.status_code == 404
    assert "could not find that location" in response.json()["detail"]


def test_geocoder_outage_is_reported_as_unavailable(db_session, patient_a):
    user, _ = patient_a
    geocoder = FakeGeocoder(error=GeocodingUnavailableError("down", cause="ReadTimeout"))
    with _authenticated_client(db_session, user, geocoder=geocoder) as client:
        response = post_search(client)

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_directory_outage_is_reported_as_unavailable(db_session, patient_a):
    user, _ = patient_a
    directory = FakeDirectory(error=ProviderLookupUnavailableError("down", cause="HTTP 503"))
    with _authenticated_client(db_session, user, directory=directory) as client:
        response = post_search(client)

    assert response.status_code == 503


def test_an_outage_is_never_reported_as_an_empty_area(db_session, patient_a):
    """
    Telling a patient "no providers near you" when the directory was simply
    unreachable would be the worst failure this feature could have.
    """
    user, _ = patient_a
    directory = FakeDirectory(error=ProviderLookupUnavailableError("down"))
    with _authenticated_client(db_session, user, directory=directory) as client:
        response = post_search(client)

    assert response.status_code != 201
    assert "recommendations" not in response.json()


def test_a_failed_search_is_not_recorded(db_session, patient_a):
    user, _ = patient_a
    directory = FakeDirectory(error=ProviderLookupUnavailableError("down"))
    with _authenticated_client(db_session, user, directory=directory) as client:
        post_search(client)
        history = client.get(HISTORY_ENDPOINT).json()

    assert history["searches"] == []


# ----------------------------------------------------------------------
# Request validation
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"location": ""},
        {"location": "   "},
        {"location": "Jaffna", "radius_km": 0},
        {"location": "Jaffna", "radius_km": 500},
        {"location": "Jaffna", "availability": "tomorrow-3pm"},
        {"location": "Jaffna", "kinds": ["dentist"]},
        {"location": "x" * 300},
    ],
)
def test_invalid_requests_are_rejected(client, body):
    assert client.post(SEARCH_ENDPOINT, json=body).status_code == 422


def test_patient_id_cannot_be_supplied_by_the_client(client, patient_b):
    """The patient is resolved from the token; smuggling one in must fail loudly."""
    _, other_patient = patient_b
    response = client.post(
        SEARCH_ENDPOINT,
        json={"location": "Jaffna", "patient_id": str(other_patient.id)},
    )

    assert response.status_code == 422


def test_availability_is_recorded_as_a_preference(client):
    body = post_search(client, availability="evenings").json()
    assert body["search"]["availability_preference"] == "evenings"


# ----------------------------------------------------------------------
# Finding linkage
# ----------------------------------------------------------------------


def _add_finding(db, patient, title="Elevated cholesterol", finding_type="lab_trend"):
    finding = Finding(
        id=uuid.uuid4(),
        patient_id=patient.id,
        finding_type=finding_type,
        title=title,
        description="Detected from records.",
    )
    db.add(finding)
    db.commit()
    return finding


def test_a_finding_drives_the_specialty(db_session, patient_a):
    user, patient = patient_a
    finding = _add_finding(db_session, patient, title="Elevated cholesterol")
    with _authenticated_client(db_session, user) as client:
        body = post_search(client, finding_id=str(finding.id)).json()

    assert body["search"]["specialty"] == "doctor:cardiology"
    assert body["search"]["finding_id"] == str(finding.id)


def test_a_search_without_a_specialty_falls_back_to_hospitals(client):
    body = post_search(client).json()
    assert body["search"]["specialty"] == "hospital"


def test_an_explicit_specialty_wins_over_the_finding(db_session, patient_a):
    user, patient = patient_a
    finding = _add_finding(db_session, patient, title="Elevated cholesterol")
    with _authenticated_client(db_session, user) as client:
        body = post_search(client, finding_id=str(finding.id), specialty="dermatology").json()

    assert body["search"]["specialty"] == "doctor:dermatology"


def test_another_patients_finding_is_not_found(db_session, patient_a, patient_b):
    user_a, _ = patient_a
    _, patient_b_record = patient_b
    b_finding = _add_finding(db_session, patient_b_record, title="Someone else's finding")

    with _authenticated_client(db_session, user_a) as client:
        response = post_search(client, finding_id=str(b_finding.id))

    assert response.status_code == 404
    assert response.json()["detail"] == "Finding not found."


def test_a_nonexistent_finding_is_not_found(client):
    response = post_search(client, finding_id=str(uuid.uuid4()))
    assert response.status_code == 404


# ----------------------------------------------------------------------
# History and retrieval
# ----------------------------------------------------------------------


def test_history_lists_recorded_searches(client):
    post_search(client, location="Jaffna")
    post_search(client, location="Colombo")

    history = client.get(HISTORY_ENDPOINT).json()
    assert len(history["searches"]) == 2


def test_repeated_searches_are_appended_not_merged(client):
    post_search(client, location="Jaffna")
    post_search(client, location="Jaffna")

    history = client.get(HISTORY_ENDPOINT).json()
    ids = {s["id"] for s in history["searches"]}
    assert len(history["searches"]) == 2 and len(ids) == 2


def test_history_honours_the_limit(client):
    for _ in range(4):
        post_search(client)

    assert len(client.get(f"{HISTORY_ENDPOINT}?limit=2").json()["searches"]) == 2


@pytest.mark.parametrize("limit", [0, -1, 1000])
def test_invalid_history_limits_are_rejected(client, limit):
    assert client.get(f"{HISTORY_ENDPOINT}?limit={limit}").status_code == 422


def test_a_recorded_search_can_be_retrieved(client):
    created = post_search(client).json()
    search_id = created["search"]["id"]

    fetched = client.get(search_endpoint(search_id))
    assert fetched.status_code == 200
    assert fetched.json()["search"]["id"] == search_id


def test_a_retrieved_search_rereads_at_the_same_scores(client):
    created = post_search(client).json()
    fetched = client.get(search_endpoint(created["search"]["id"])).json()

    assert [r["match_score"] for r in fetched["recommendations"]] == [
        r["match_score"] for r in created["recommendations"]
    ]


def test_an_unknown_search_is_not_found(client):
    assert client.get(search_endpoint(uuid.uuid4())).status_code == 404


def test_a_malformed_search_id_is_rejected(client):
    assert client.get(search_endpoint("not-a-uuid")).status_code == 422


# ----------------------------------------------------------------------
# Cross-patient isolation
# ----------------------------------------------------------------------


def test_a_patient_cannot_retrieve_another_patients_search(db_session, patient_a, patient_b):
    user_a, _ = patient_a
    user_b, _ = patient_b

    with _authenticated_client(db_session, user_b) as client_b:
        b_search_id = post_search(client_b, location="Colombo").json()["search"]["id"]

    with _authenticated_client(db_session, user_a) as client_a:
        leaked = client_a.get(search_endpoint(b_search_id))

    assert leaked.status_code == 404

    # ...and the owner can still read it, so the filter is not simply broken.
    with _authenticated_client(db_session, user_b) as client_b:
        assert client_b.get(search_endpoint(b_search_id)).status_code == 200


def test_history_never_shows_another_patients_searches(db_session, patient_a, patient_b):
    user_a, _ = patient_a
    user_b, _ = patient_b

    with _authenticated_client(db_session, user_b) as client_b:
        post_search(client_b, location="Colombo")

    with _authenticated_client(db_session, user_a) as client_a:
        post_search(client_a, location="Jaffna")
        history = client_a.get(HISTORY_ENDPOINT).json()

    locations = [s["location_query"] for s in history["searches"]]
    assert locations == ["Jaffna"]
    assert "Colombo" not in locations


def test_another_patients_search_is_indistinguishable_from_a_missing_one(
    db_session, patient_a, patient_b
):
    """A 404 must not reveal that another patient's search id is real."""
    user_a, _ = patient_a
    user_b, _ = patient_b

    with _authenticated_client(db_session, user_b) as client_b:
        b_search_id = post_search(client_b).json()["search"]["id"]

    with _authenticated_client(db_session, user_a) as client_a:
        not_theirs = client_a.get(search_endpoint(b_search_id))
        never_existed = client_a.get(search_endpoint(uuid.uuid4()))

    assert not_theirs.status_code == never_existed.status_code == 404
    assert not_theirs.json() == never_existed.json()


def test_no_response_exposes_a_patient_identifier(client):
    created = post_search(client).json()
    history = client.get(HISTORY_ENDPOINT).json()

    for body in (created, history):
        assert "patient_id" not in str(body)


# ----------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------


def test_search_requires_authentication(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_geocoder] = lambda: FakeGeocoder()
    app.dependency_overrides[get_directory] = lambda: FakeDirectory([HOSPITAL])
    try:
        with TestClient(app) as unauthenticated:
            assert unauthenticated.post(SEARCH_ENDPOINT, json={"location": "Jaffna"}).status_code == 401
            assert unauthenticated.get(HISTORY_ENDPOINT).status_code == 401
            assert unauthenticated.get(search_endpoint(uuid.uuid4())).status_code == 401
    finally:
        app.dependency_overrides.clear()


# ----------------------------------------------------------------------
# Route registration
# ----------------------------------------------------------------------


def test_routes_are_registered_under_the_api_prefix():
    """
    Asserts against the generated OpenAPI schema rather than app.routes, so this
    also proves the endpoints are published on /docs and not merely mounted.
    """
    paths = app.openapi()["paths"]

    assert SEARCH_ENDPOINT in paths
    assert HISTORY_ENDPOINT in paths
    assert "/api/doctor-search/searches/{search_id}" in paths
    assert "post" in paths[SEARCH_ENDPOINT]
    assert "get" in paths[HISTORY_ENDPOINT]


def test_registering_the_router_did_not_disturb_the_other_features():
    paths = app.openapi()["paths"]

    for existing in ("/api/records/overview", "/api/lab-intelligence/overview", "/api/documents"):
        assert existing in paths
