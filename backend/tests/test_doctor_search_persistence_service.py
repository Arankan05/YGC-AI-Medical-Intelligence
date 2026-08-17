"""
Tests for the doctor-search persistence layer.

These run against a real SQLite session rather than a mocked one, following the
pattern in test_lab_intelligence_api.py: the isolation guarantees are enforced
by SQL filters, and asserting them is only meaningful if those filters actually
execute.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  - registers every table on Base.metadata
from app.db.database import Base
from app.models.doctor_recommendation import DoctorRecommendation
from app.models.doctor_search import DoctorSearch
from app.models.finding import Finding
from app.models.patient import Patient
from app.models.user import User
from app.services.doctor_search_persistence_service import (
    DoctorSearchPersistenceService,
    get_doctor_search_persistence_service,
)
from app.services.provider_discovery_service import (
    KIND_CLINIC,
    KIND_DOCTOR,
    KIND_HOSPITAL,
    KIND_PHARMACY,
    ProviderCandidate,
    RankedProvider,
    get_provider_discovery_service,
)

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def service() -> DoctorSearchPersistenceService:
    return DoctorSearchPersistenceService()


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
    return _create_patient(db_session, "patient_a@example.com")[1]


@pytest.fixture
def patient_b(db_session):
    return _create_patient(db_session, "patient_b@example.com")[1]


def make_candidate(**overrides) -> ProviderCandidate:
    base = dict(
        name="Jaffna Teaching Hospital",
        kind=KIND_HOSPITAL,
        latitude=9.6698,
        longitude=80.0206,
        address="Hospital Road, Jaffna",
        phone="+94 21 222 3348",
        website="https://example.org",
        opening_hours="24/7",
        specialties=(),
        source="openstreetmap",
        source_element_id="node/1",
    )
    base.update(overrides)
    return ProviderCandidate(**base)


def make_ranked(candidate=None, distance_km=2.1) -> RankedProvider:
    """Builds a ranked provider using the real scorer, not a hand-made score."""
    discovery = get_provider_discovery_service()
    candidate = candidate or make_candidate()
    breakdown = discovery.score(
        candidate, KIND_HOSPITAL, distance_km=distance_km, radius_km=10.0
    )
    return RankedProvider(
        candidate=candidate,
        distance_km=distance_km,
        match_score=breakdown.total,
        match_breakdown=breakdown,
    )


def record(service, db, patient, **overrides):
    kwargs = dict(
        patient_id=patient.id,
        location_query="Jaffna",
        requested_kind=KIND_HOSPITAL,
        latitude=9.6615,
        longitude=80.0255,
        search_radius=10.0,
        ranked=[make_ranked()],
    )
    kwargs.update(overrides)
    return service.record_search(db, **kwargs)


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------


def test_records_a_search_with_its_results(service, db_session, patient_a):
    search = record(service, db_session, patient_a)

    assert search.id is not None
    assert search.patient_id == patient_a.id
    assert search.location_query == "Jaffna"
    assert search.latitude == pytest.approx(9.6615)
    assert search.search_radius == 10.0
    assert len(search.recommendations) == 1


def test_recommendation_fields_come_from_the_source(service, db_session, patient_a):
    search = record(service, db_session, patient_a)
    rec = search.recommendations[0]

    assert rec.provider_name == "Jaffna Teaching Hospital"
    assert rec.address == "Hospital Road, Jaffna"
    assert rec.phone == "+94 21 222 3348"
    assert rec.opening_hours == "24/7"
    assert rec.distance_km == pytest.approx(2.1)
    assert rec.source == "openstreetmap"


def test_unpublished_details_are_stored_as_null_not_placeholders(service, db_session, patient_a):
    bare = make_candidate(phone=None, website=None, opening_hours=None, address=None)
    search = record(service, db_session, patient_a, ranked=[make_ranked(bare)])
    rec = search.recommendations[0]

    assert rec.phone is None
    assert rec.website is None
    assert rec.opening_hours is None
    assert rec.address is None


def test_search_scope_is_encoded_on_the_search(service, db_session, patient_a):
    search = record(
        service, db_session, patient_a,
        requested_kind=KIND_DOCTOR, requested_specialty="cardiology",
    )
    assert search.specialty == "doctor:cardiology"


def test_hospital_search_encodes_as_a_bare_kind(service, db_session, patient_a):
    search = record(service, db_session, patient_a, requested_kind=KIND_HOSPITAL)
    assert search.specialty == "hospital"


def test_recommendation_scope_records_the_providers_own_specialty(service, db_session, patient_a):
    candidate = make_candidate(kind=KIND_DOCTOR, specialties=("cardiology",))
    search = record(
        service, db_session, patient_a,
        requested_kind=KIND_DOCTOR, requested_specialty="cardiology",
        ranked=[make_ranked(candidate)],
    )
    assert search.recommendations[0].specialty == "doctor:cardiology"


def test_requested_specialty_is_never_written_onto_a_provider_that_lacks_it(
    service, db_session, patient_a
):
    """
    The search asks for cardiology; the provider publishes no specialty. The
    stored scope must not claim one - that would be inventing clinical data.
    """
    silent = make_candidate(kind=KIND_DOCTOR, specialties=())
    search = record(
        service, db_session, patient_a,
        requested_kind=KIND_DOCTOR, requested_specialty="cardiology",
        ranked=[make_ranked(silent)],
    )

    assert search.specialty == "doctor:cardiology"
    assert search.recommendations[0].specialty == "doctor"


def test_only_the_first_published_specialty_is_retained(service, db_session, patient_a):
    candidate = make_candidate(kind=KIND_DOCTOR, specialties=("cardiology", "general"))
    search = record(service, db_session, patient_a, ranked=[make_ranked(candidate)])
    assert search.recommendations[0].specialty == "doctor:cardiology"


def test_provider_without_a_name_is_skipped_not_given_a_placeholder(service, db_session, patient_a):
    nameless = make_candidate(name="   ")
    search = record(service, db_session, patient_a, ranked=[make_ranked(nameless)])
    assert search.recommendations == []


def test_a_search_with_no_results_is_still_recorded(service, db_session, patient_a):
    search = record(service, db_session, patient_a, ranked=[])
    assert search.id is not None
    assert search.recommendations == []


def test_long_values_are_truncated_to_the_column_limits(service, db_session, patient_a):
    candidate = make_candidate(name="N" * 400, phone="0" * 120, website="https://" + "w" * 800)
    search = record(
        service, db_session, patient_a,
        location_query="L" * 400,
        ranked=[make_ranked(candidate)],
    )
    rec = search.recommendations[0]

    assert len(search.location_query) <= 255
    assert len(rec.provider_name) <= 255
    assert len(rec.phone) <= 50
    assert len(rec.website) <= 500


# ----------------------------------------------------------------------
# Append-only history
# ----------------------------------------------------------------------


def test_repeating_a_search_appends_rather_than_overwrites(service, db_session, patient_a):
    first = record(service, db_session, patient_a)
    second = record(service, db_session, patient_a)

    assert first.id != second.id
    assert db_session.query(DoctorSearch).filter(
        DoctorSearch.patient_id == patient_a.id
    ).count() == 2


def test_history_is_not_capped(service, db_session, patient_a):
    for _ in range(12):
        record(service, db_session, patient_a)

    assert len(service.list_searches(db_session, patient_id=patient_a.id)) == 12


def test_list_searches_can_be_limited_by_the_caller(service, db_session, patient_a):
    for _ in range(5):
        record(service, db_session, patient_a)

    assert len(service.list_searches(db_session, patient_id=patient_a.id, limit=2)) == 2


# ----------------------------------------------------------------------
# Cross-patient isolation
# ----------------------------------------------------------------------


def test_a_patient_only_lists_their_own_searches(service, db_session, patient_a, patient_b):
    record(service, db_session, patient_a, location_query="Jaffna")
    record(service, db_session, patient_b, location_query="Colombo")

    a_searches = service.list_searches(db_session, patient_id=patient_a.id)
    b_searches = service.list_searches(db_session, patient_id=patient_b.id)

    assert [s.location_query for s in a_searches] == ["Jaffna"]
    assert [s.location_query for s in b_searches] == ["Colombo"]


def test_a_patient_cannot_read_another_patients_search(service, db_session, patient_a, patient_b):
    b_search = record(service, db_session, patient_b, location_query="Colombo")

    assert service.get_search(db_session, patient_id=patient_a.id, search_id=b_search.id) is None
    # ...and the owner can still read it, so the filter is not simply broken.
    assert service.get_search(db_session, patient_id=patient_b.id, search_id=b_search.id) is not None


def test_a_missing_search_is_indistinguishable_from_another_patients(
    service, db_session, patient_a, patient_b
):
    b_search = record(service, db_session, patient_b)

    not_theirs = service.get_search(db_session, patient_id=patient_a.id, search_id=b_search.id)
    never_existed = service.get_search(db_session, patient_id=patient_a.id, search_id=uuid.uuid4())

    assert not_theirs is None and never_existed is None


def test_recommendations_are_scoped_through_the_owning_search(
    service, db_session, patient_a, patient_b
):
    """
    DoctorRecommendation has no patient_id of its own. Reading it without
    joining DoctorSearch would expose every patient's providers.
    """
    b_search = record(service, db_session, patient_b)

    leaked = service.list_recommendations(
        db_session, patient_id=patient_a.id, search_id=b_search.id
    )
    owned = service.list_recommendations(
        db_session, patient_id=patient_b.id, search_id=b_search.id
    )

    assert leaked == []
    assert len(owned) == 1


def test_counting_another_patients_results_returns_zero(service, db_session, patient_a, patient_b):
    b_search = record(service, db_session, patient_b)

    assert service.count_recommendations(
        db_session, patient_id=patient_a.id, search_id=b_search.id
    ) == 0
    assert service.count_recommendations(
        db_session, patient_id=patient_b.id, search_id=b_search.id
    ) == 1


def test_loading_a_scored_search_is_also_scoped(service, db_session, patient_a, patient_b):
    b_search = record(service, db_session, patient_b)

    assert service.load_scored_search(
        db_session, patient_id=patient_a.id, search_id=b_search.id
    ) is None
    assert service.load_scored_search(
        db_session, patient_id=patient_b.id, search_id=b_search.id
    ) is not None


def test_one_patients_write_does_not_touch_anothers_rows(service, db_session, patient_a, patient_b):
    a_search = record(service, db_session, patient_a)
    record(service, db_session, patient_b)

    still_a = db_session.query(DoctorSearch).filter(DoctorSearch.id == a_search.id).first()
    assert still_a is not None and still_a.patient_id == patient_a.id


# ----------------------------------------------------------------------
# Finding linkage
# ----------------------------------------------------------------------


def _add_finding(db, patient, title="Elevated cholesterol"):
    finding = Finding(
        id=uuid.uuid4(),
        patient_id=patient.id,
        finding_type="lab_trend",
        title=title,
        description="Detected from records.",
    )
    db.add(finding)
    db.commit()
    return finding


def test_a_finding_belonging_to_the_patient_is_linked(service, db_session, patient_a):
    finding = _add_finding(db_session, patient_a)
    search = record(service, db_session, patient_a, finding_id=finding.id)
    assert search.finding_id == finding.id


def test_another_patients_finding_is_never_linked(service, db_session, patient_a, patient_b):
    b_finding = _add_finding(db_session, patient_b, title="Someone else's finding")

    search = record(service, db_session, patient_a, finding_id=b_finding.id)

    # The search is still recorded - it is a legitimate search - but it must not
    # point at another patient's clinical finding.
    assert search.id is not None
    assert search.finding_id is None


def test_a_nonexistent_finding_is_not_linked(service, db_session, patient_a):
    search = record(service, db_session, patient_a, finding_id=uuid.uuid4())
    assert search.finding_id is None


def test_no_finding_link_is_the_default(service, db_session, patient_a):
    assert record(service, db_session, patient_a).finding_id is None


# ----------------------------------------------------------------------
# Scores are recomputed, not stored
# ----------------------------------------------------------------------


def test_no_score_is_written_to_the_database(service, db_session, patient_a):
    record(service, db_session, patient_a)
    columns = {c.name for c in DoctorRecommendation.__table__.columns}

    assert "match_score" not in columns
    assert "match_breakdown" not in columns


def test_a_stored_search_rereads_at_the_score_it_was_created_with(
    service, db_session, patient_a
):
    candidate = make_candidate(kind=KIND_HOSPITAL)
    ranked = make_ranked(candidate, distance_km=2.1)
    search = record(service, db_session, patient_a, ranked=[ranked])

    loaded, scored = service.load_scored_search(
        db_session, patient_id=patient_a.id, search_id=search.id
    )

    assert scored[0].match_score == ranked.match_score
    assert scored[0].match_breakdown == ranked.match_breakdown


def test_rescoring_is_stable_across_repeated_reads(service, db_session, patient_a):
    search = record(service, db_session, patient_a)

    first = service.load_scored_search(db_session, patient_id=patient_a.id, search_id=search.id)[1]
    second = service.load_scored_search(db_session, patient_id=patient_a.id, search_id=search.id)[1]

    assert [s.match_score for s in first] == [s.match_score for s in second]


def test_scored_results_are_ordered_best_first(service, db_session, patient_a):
    near = make_candidate(name="Near Hospital", kind=KIND_HOSPITAL)
    far = make_candidate(name="Far Pharmacy", kind=KIND_PHARMACY,
                         phone=None, website=None, opening_hours=None, address=None)
    search = record(
        service, db_session, patient_a,
        ranked=[make_ranked(far, distance_km=9.0), make_ranked(near, distance_km=1.0)],
    )

    _, scored = service.load_scored_search(
        db_session, patient_id=patient_a.id, search_id=search.id
    )

    assert [s.recommendation.provider_name for s in scored] == ["Near Hospital", "Far Pharmacy"]
    assert scored[0].match_score >= scored[1].match_score


def test_kind_and_specialties_are_decoded_on_read(service, db_session, patient_a):
    candidate = make_candidate(kind=KIND_DOCTOR, specialties=("cardiology",))
    search = record(service, db_session, patient_a, ranked=[make_ranked(candidate)])

    _, scored = service.load_scored_search(
        db_session, patient_id=patient_a.id, search_id=search.id
    )

    assert scored[0].kind == KIND_DOCTOR
    assert scored[0].specialties == ("cardiology",)


def test_a_clinic_result_round_trips(service, db_session, patient_a):
    candidate = make_candidate(kind=KIND_CLINIC, specialties=())
    search = record(service, db_session, patient_a, ranked=[make_ranked(candidate)])

    _, scored = service.load_scored_search(
        db_session, patient_id=patient_a.id, search_id=search.id
    )

    assert scored[0].kind == KIND_CLINIC
    assert scored[0].specialties == ()


def test_an_unreadable_scope_scores_zero_rather_than_being_guessed(service, db_session, patient_a):
    search = record(service, db_session, patient_a)
    rec = search.recommendations[0]
    rec.specialty = "dentist:orthodontics"  # not a category this feature knows
    db_session.commit()

    _, scored = service.load_scored_search(
        db_session, patient_id=patient_a.id, search_id=search.id
    )

    assert scored[0].kind is None
    assert scored[0].match_breakdown.specialty == 0.0


def test_candidate_rebuilt_from_a_row_keeps_every_published_field(service, db_session, patient_a):
    search = record(service, db_session, patient_a)
    candidate = service.to_candidate(search.recommendations[0])

    assert candidate.name == "Jaffna Teaching Hospital"
    assert candidate.kind == KIND_HOSPITAL
    assert candidate.phone == "+94 21 222 3348"
    assert candidate.opening_hours == "24/7"
    assert candidate.source == "openstreetmap"


# ----------------------------------------------------------------------
# Cascade behaviour
# ----------------------------------------------------------------------


def test_deleting_a_search_removes_its_recommendations(service, db_session, patient_a):
    search = record(service, db_session, patient_a)
    search_id = search.id

    db_session.delete(search)
    db_session.commit()

    assert db_session.query(DoctorRecommendation).filter(
        DoctorRecommendation.doctor_search_id == search_id
    ).count() == 0


# ----------------------------------------------------------------------
# Accessor
# ----------------------------------------------------------------------


def test_accessor_returns_a_shared_instance():
    assert get_doctor_search_persistence_service() is get_doctor_search_persistence_service()
