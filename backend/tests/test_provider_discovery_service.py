"""
Tests for the pure provider discovery and ranking logic.

Every test here runs offline. The service performs no I/O, so nothing is mocked
and no network call, database session or fixture server is involved.
"""

import math

import pytest

from app.services.provider_discovery_service import (
    COMPLETENESS_WEIGHT,
    DISTANCE_WEIGHT,
    KIND_CLINIC,
    KIND_DOCTOR,
    KIND_HOSPITAL,
    KIND_LABORATORY,
    KIND_PHARMACY,
    SOURCE_OPENSTREETMAP,
    SPECIALTY_WEIGHT,
    VERIFIED_WEIGHT,
    ProviderCandidate,
    ProviderDiscoveryService,
    get_provider_discovery_service,
)


@pytest.fixture
def service() -> ProviderDiscoveryService:
    return ProviderDiscoveryService()


def make_candidate(**overrides) -> ProviderCandidate:
    """A fully-populated candidate; override individual fields per test."""
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
        source=SOURCE_OPENSTREETMAP,
        source_element_id="node/1",
    )
    base.update(overrides)
    return ProviderCandidate(**base)


# ----------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------


def test_haversine_zero_for_identical_points(service):
    assert service.haversine_km(9.6615, 80.0255, 9.6615, 80.0255) == 0.0


def test_haversine_matches_known_distance(service):
    # Colombo -> Jaffna is roughly 300 km great-circle.
    km = service.haversine_km(6.9271, 79.8612, 9.6615, 80.0255)
    assert 300 <= km <= 310


def test_haversine_is_symmetric(service):
    forward = service.haversine_km(9.66, 80.02, 9.70, 80.05)
    backward = service.haversine_km(9.70, 80.05, 9.66, 80.02)
    assert forward == pytest.approx(backward)


def test_haversine_one_degree_of_latitude_is_about_111_km(service):
    assert service.haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.19, abs=0.1)


def test_distance_from_returns_none_without_origin(service):
    assert service.distance_from(None, None, make_candidate()) is None


def test_distance_from_returns_none_when_candidate_has_no_coordinates(service):
    candidate = make_candidate(latitude=None, longitude=None)
    assert service.distance_from(9.66, 80.02, candidate) is None


def test_distance_from_computes_distance(service):
    candidate = make_candidate(latitude=9.6615, longitude=80.0255)
    distance = service.distance_from(9.6698, 80.0206, candidate)
    assert distance is not None and 0 < distance < 2


# ----------------------------------------------------------------------
# Search scope encoding
# ----------------------------------------------------------------------


def test_hospital_search_encodes_to_bare_kind(service):
    assert service.build_search_scope(KIND_HOSPITAL) == "hospital"


def test_doctor_search_with_specialty_encodes_with_suffix(service):
    assert service.build_search_scope(KIND_DOCTOR, "cardiology") == "doctor:cardiology"
    assert service.build_search_scope(KIND_DOCTOR, "Dermatology") == "doctor:dermatology"
    assert service.build_search_scope(KIND_DOCTOR, " Neurology ") == "doctor:neurology"


def test_hospital_scope_decodes_to_hospital_kind(service):
    assert service.parse_search_scope("hospital") == (KIND_HOSPITAL, ())


def test_doctor_scope_decodes_to_kind_and_specialty(service):
    assert service.parse_search_scope("doctor:cardiology") == (KIND_DOCTOR, ("cardiology",))


@pytest.mark.parametrize(
    "kind,specialty",
    [
        (KIND_HOSPITAL, None),
        (KIND_DOCTOR, "cardiology"),
        (KIND_DOCTOR, "dermatology"),
        (KIND_DOCTOR, "neurology"),
        (KIND_CLINIC, None),
        (KIND_PHARMACY, None),
        (KIND_LABORATORY, "histopathology"),
    ],
)
def test_scope_round_trips(service, kind, specialty):
    scope = service.build_search_scope(kind, specialty)
    decoded_kind, decoded_specialties = service.parse_search_scope(scope)
    assert decoded_kind == kind
    assert decoded_specialties == ((specialty,) if specialty else ())


def test_blank_specialty_is_not_encoded(service):
    assert service.build_search_scope(KIND_DOCTOR, "   ") == "doctor"
    assert service.build_search_scope(KIND_DOCTOR, None) == "doctor"


def test_unknown_kind_is_rejected(service):
    with pytest.raises(ValueError):
        service.build_search_scope("dentist")


def test_unrecognised_scope_decodes_to_none_rather_than_a_guess(service):
    assert service.parse_search_scope("dentist:orthodontics") == (None, ())
    assert service.parse_search_scope("") == (None, ())
    assert service.parse_search_scope(None) == (None, ())


def test_encoded_scope_fits_the_specialty_column(service):
    scope = service.build_search_scope(KIND_LABORATORY, "x" * 300)
    assert len(scope) <= 100
    assert service.parse_search_scope(scope)[0] == KIND_LABORATORY


def test_specialty_separator_cannot_break_decoding(service):
    scope = service.build_search_scope(KIND_DOCTOR, "cardio:logy")
    assert scope.count(":") == 1
    assert service.parse_search_scope(scope) == (KIND_DOCTOR, ("cardio-logy",))


# ----------------------------------------------------------------------
# Specialty derivation
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Elevated cholesterol detected", "cardiology"),
        ("HbA1c indicates diabetes risk", "endocrinology"),
        ("Declining eGFR / kidney function", "nephrology"),
        ("Persistent asthma symptoms", "pulmonology"),
        ("Raised ALT suggests liver strain", "gastroenterology"),
        ("Recurrent migraine episodes", "neurology"),
        ("Chronic skin rash", "dermatology"),
    ],
)
def test_specialty_derived_from_finding_text(service, text, expected):
    assert service.derive_specialty(title=text) == expected


def test_specialty_derivation_returns_none_when_nothing_matches(service):
    assert service.derive_specialty(title="Routine annual review") is None
    assert service.derive_specialty() is None
    assert service.derive_specialty(finding_type="", title="", description="") is None


def test_specialty_derivation_reads_all_provided_fields(service):
    assert service.derive_specialty(finding_type="lab_trend", description="thyroid") == "endocrinology"


# ----------------------------------------------------------------------
# Overpass parsing
# ----------------------------------------------------------------------


def test_parses_a_fully_tagged_node(service):
    element = {
        "type": "node",
        "id": 42,
        "lat": 9.6698,
        "lon": 80.0206,
        "tags": {
            "amenity": "hospital",
            "name": "Jaffna Teaching Hospital",
            "phone": "+94 21 222 3348",
            "website": "https://example.org",
            "opening_hours": "24/7",
            "addr:housenumber": "12",
            "addr:street": "Hospital Road",
            "addr:city": "Jaffna",
            "healthcare:speciality": "cardiology;general",
        },
    }
    candidate = service.parse_overpass_element(element)

    assert candidate is not None
    assert candidate.name == "Jaffna Teaching Hospital"
    assert candidate.kind == KIND_HOSPITAL
    assert candidate.latitude == 9.6698
    assert candidate.address == "12 Hospital Road, Jaffna"
    assert candidate.specialties == ("cardiology", "general")
    assert candidate.source == SOURCE_OPENSTREETMAP
    assert candidate.source_element_id == "node/42"


def test_unpublished_details_stay_none_and_are_never_invented(service):
    element = {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0,
               "tags": {"amenity": "pharmacy", "name": "Green Cross"}}
    candidate = service.parse_overpass_element(element)

    assert candidate is not None
    assert candidate.kind == KIND_PHARMACY
    assert candidate.phone is None
    assert candidate.website is None
    assert candidate.opening_hours is None
    assert candidate.address is None
    assert candidate.specialties == ()


def test_element_without_a_name_is_discarded(service):
    element = {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0, "tags": {"amenity": "clinic"}}
    assert service.parse_overpass_element(element) is None


def test_operator_is_used_when_no_name_is_published(service):
    element = {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0,
               "tags": {"amenity": "clinic", "operator": "Ministry of Health"}}
    candidate = service.parse_overpass_element(element)
    assert candidate is not None and candidate.name == "Ministry of Health"


def test_non_healthcare_element_is_discarded(service):
    element = {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0,
               "tags": {"amenity": "restaurant", "name": "Not A Clinic"}}
    assert service.parse_overpass_element(element) is None


@pytest.mark.parametrize(
    "tags,expected",
    [
        ({"amenity": "hospital"}, KIND_HOSPITAL),
        ({"amenity": "clinic"}, KIND_CLINIC),
        ({"amenity": "doctors"}, KIND_DOCTOR),
        ({"amenity": "pharmacy"}, KIND_PHARMACY),
        ({"healthcare": "laboratory"}, KIND_LABORATORY),
        ({"healthcare": "centre"}, KIND_CLINIC),
        ({"healthcare": "doctor"}, KIND_DOCTOR),
    ],
)
def test_kind_is_read_from_amenity_or_healthcare_tags(service, tags, expected):
    element = {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0, "tags": {**tags, "name": "X"}}
    candidate = service.parse_overpass_element(element)
    assert candidate is not None and candidate.kind == expected


def test_way_coordinates_come_from_the_computed_centre(service):
    element = {"type": "way", "id": 7, "center": {"lat": 9.5, "lon": 80.1},
               "tags": {"amenity": "hospital", "name": "Central"}}
    candidate = service.parse_overpass_element(element)
    assert candidate is not None
    assert (candidate.latitude, candidate.longitude) == (9.5, 80.1)
    assert candidate.source_element_id == "way/7"


def test_contact_prefixed_tags_are_read(service):
    element = {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0,
               "tags": {"amenity": "clinic", "name": "X",
                        "contact:phone": "+94 11 000", "contact:website": "https://e.org"}}
    candidate = service.parse_overpass_element(element)
    assert candidate is not None
    assert candidate.phone == "+94 11 000"
    assert candidate.website == "https://e.org"


def test_malformed_coordinates_are_treated_as_absent(service):
    element = {"type": "node", "id": 1, "lat": "not-a-number", "lon": 2.0,
               "tags": {"amenity": "clinic", "name": "X"}}
    candidate = service.parse_overpass_element(element)
    assert candidate is not None and candidate.latitude is None


def test_response_parsing_skips_unreadable_elements(service):
    payload = {"elements": [
        {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0, "tags": {"amenity": "clinic", "name": "Good"}},
        {"type": "node", "id": 2, "tags": {"amenity": "restaurant", "name": "Bad"}},
        "not-a-dict",
        {"no": "tags"},
    ]}
    candidates = service.parse_overpass_response(payload)
    assert [c.name for c in candidates] == ["Good"]


def test_duplicate_elements_are_collapsed(service):
    element = {"type": "node", "id": 1, "lat": 1.0, "lon": 2.0,
               "tags": {"amenity": "clinic", "name": "Twice"}}
    candidates = service.parse_overpass_response({"elements": [element, dict(element)]})
    assert len(candidates) == 1


@pytest.mark.parametrize("payload", [None, {}, [], "text", {"elements": "nope"}, {"elements": None}])
def test_malformed_payload_yields_no_results_rather_than_an_error(service, payload):
    assert service.parse_overpass_response(payload) == []


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------


def test_weights_sum_to_one_hundred():
    assert SPECIALTY_WEIGHT + DISTANCE_WEIGHT + COMPLETENESS_WEIGHT + VERIFIED_WEIGHT == 100.0


def test_perfect_match_scores_one_hundred(service):
    candidate = make_candidate(kind=KIND_DOCTOR, specialties=("cardiology",))
    breakdown = service.score(candidate, KIND_DOCTOR, "cardiology",
                              distance_km=0.0, radius_km=10.0)
    assert breakdown.total == 100.0
    assert breakdown.specialty == SPECIALTY_WEIGHT
    assert breakdown.distance == DISTANCE_WEIGHT


def test_breakdown_always_sums_to_the_score(service):
    candidate = make_candidate(kind=KIND_CLINIC, specialties=("dermatology",))
    breakdown = service.score(candidate, KIND_DOCTOR, "cardiology",
                              distance_km=3.2, radius_km=10.0)
    manual = round(
        breakdown.specialty + breakdown.distance + breakdown.completeness + breakdown.verified, 2
    )
    assert breakdown.total == manual


def test_score_never_leaves_the_zero_to_one_hundred_range(service):
    for kind in (KIND_HOSPITAL, KIND_CLINIC, KIND_DOCTOR, KIND_PHARMACY, KIND_LABORATORY):
        for distance in (0.0, 1.0, 9.9, 10.0, 500.0, None):
            candidate = make_candidate(kind=kind)
            breakdown = service.score(candidate, KIND_DOCTOR, "cardiology",
                                      distance_km=distance, radius_km=10.0)
            assert 0.0 <= breakdown.total <= 100.0


def test_unconfirmed_specialty_scores_lower_than_a_published_one(service):
    published = make_candidate(kind=KIND_DOCTOR, specialties=("cardiology",))
    silent = make_candidate(kind=KIND_DOCTOR, specialties=())

    high = service.score(published, KIND_DOCTOR, "cardiology", distance_km=1.0, radius_km=10.0)
    low = service.score(silent, KIND_DOCTOR, "cardiology", distance_km=1.0, radius_km=10.0)

    assert high.specialty > low.specialty
    assert low.specialty > 0  # the category still matches, so it is not disqualified


def test_unrelated_category_scores_no_specialty_points(service):
    pharmacy = make_candidate(kind=KIND_PHARMACY)
    breakdown = service.score(pharmacy, KIND_DOCTOR, distance_km=1.0, radius_km=10.0)
    assert breakdown.specialty == 0.0


def test_distance_points_decay_with_distance(service):
    candidate = make_candidate()
    near = service.score(candidate, KIND_HOSPITAL, distance_km=1.0, radius_km=10.0)
    far = service.score(candidate, KIND_HOSPITAL, distance_km=8.0, radius_km=10.0)
    assert near.distance > far.distance


def test_distance_points_are_zero_at_and_beyond_the_radius(service):
    candidate = make_candidate()
    at_edge = service.score(candidate, KIND_HOSPITAL, distance_km=10.0, radius_km=10.0)
    beyond = service.score(candidate, KIND_HOSPITAL, distance_km=25.0, radius_km=10.0)
    assert at_edge.distance == 0.0 and beyond.distance == 0.0


def test_unknown_distance_scores_zero_not_an_average(service):
    candidate = make_candidate(latitude=None, longitude=None)
    breakdown = service.score(candidate, KIND_HOSPITAL, distance_km=None, radius_km=10.0)
    assert breakdown.distance == 0.0


def test_completeness_rewards_published_contact_details(service):
    complete = make_candidate()
    bare = make_candidate(phone=None, website=None, opening_hours=None)
    assert service.score(complete, KIND_HOSPITAL).completeness == COMPLETENESS_WEIGHT
    assert service.score(bare, KIND_HOSPITAL).completeness == 0.0


def test_availability_shifts_weight_towards_published_hours(service):
    hours_only = make_candidate(phone=None, website=None, opening_hours="Mo-Fr 17:00-21:00")

    without = service.score(hours_only, KIND_HOSPITAL)
    with_preference = service.score(hours_only, KIND_HOSPITAL, availability_preference="evenings")

    assert with_preference.completeness > without.completeness


def test_availability_never_changes_the_completeness_ceiling(service):
    complete = make_candidate()
    assert service.score(complete, KIND_HOSPITAL).completeness == COMPLETENESS_WEIGHT
    assert service.score(
        complete, KIND_HOSPITAL, availability_preference="weekends"
    ).completeness == COMPLETENESS_WEIGHT


def test_verified_rewards_record_quality(service):
    full = make_candidate(specialties=("cardiology",))
    sparse = make_candidate(latitude=None, longitude=None, address=None, specialties=())
    assert service.score(full, KIND_HOSPITAL).verified == VERIFIED_WEIGHT
    assert service.score(sparse, KIND_HOSPITAL).verified == 0.0


def test_scoring_is_reproducible(service):
    candidate = make_candidate(kind=KIND_CLINIC, specialties=("cardiology",))
    args = dict(requested_kind=KIND_DOCTOR, requested_specialty="cardiology",
                distance_km=2.5, radius_km=10.0, availability_preference="evenings")
    first = service.score(candidate, **args)
    second = service.score(candidate, **args)
    assert first == second


def test_two_service_instances_agree(service):
    candidate = make_candidate()
    other = ProviderDiscoveryService()
    assert service.score(candidate, KIND_HOSPITAL, distance_km=1.0, radius_km=10.0) == other.score(
        candidate, KIND_HOSPITAL, distance_km=1.0, radius_km=10.0
    )


# ----------------------------------------------------------------------
# Ranking
# ----------------------------------------------------------------------


def test_ranking_orders_by_descending_score(service):
    near_doctor = make_candidate(name="Near Doctor", kind=KIND_DOCTOR,
                                 latitude=9.6700, longitude=80.0210, specialties=("cardiology",))
    far_pharmacy = make_candidate(name="Far Pharmacy", kind=KIND_PHARMACY,
                                  latitude=9.7500, longitude=80.1000)

    ranked = service.rank([far_pharmacy, near_doctor], KIND_DOCTOR, "cardiology",
                          origin_lat=9.6698, origin_lon=80.0206, radius_km=25.0)

    assert [r.candidate.name for r in ranked] == ["Near Doctor", "Far Pharmacy"]
    assert ranked[0].match_score > ranked[1].match_score


def test_ranking_never_drops_a_real_provider(service):
    weak = make_candidate(name="Weak", kind=KIND_PHARMACY, latitude=None, longitude=None,
                          address=None, phone=None, website=None, opening_hours=None)
    strong = make_candidate(name="Strong", kind=KIND_DOCTOR)

    ranked = service.rank([weak, strong], KIND_DOCTOR,
                          origin_lat=9.66, origin_lon=80.02, radius_km=10.0)

    assert len(ranked) == 2
    assert ranked[-1].candidate.name == "Weak"
    assert ranked[-1].match_score == 0.0


def test_ranking_is_stable_for_identical_scores(service):
    a = make_candidate(name="Alpha Clinic", kind=KIND_CLINIC, source_element_id="node/1")
    b = make_candidate(name="Beta Clinic", kind=KIND_CLINIC, source_element_id="node/2")

    forward = service.rank([a, b], KIND_CLINIC, radius_km=10.0)
    reversed_ = service.rank([b, a], KIND_CLINIC, radius_km=10.0)

    assert [r.candidate.name for r in forward] == [r.candidate.name for r in reversed_]


def test_ranking_sets_distance_on_each_result(service):
    candidate = make_candidate(latitude=9.6615, longitude=80.0255)
    ranked = service.rank([candidate], KIND_HOSPITAL,
                          origin_lat=9.6698, origin_lon=80.0206, radius_km=10.0)
    assert ranked[0].distance_km is not None and ranked[0].distance_km > 0


def test_ranking_leaves_distance_none_without_an_origin(service):
    ranked = service.rank([make_candidate()], KIND_HOSPITAL, radius_km=10.0)
    assert ranked[0].distance_km is None


def test_ranking_an_empty_list_returns_an_empty_list(service):
    assert service.rank([], KIND_HOSPITAL, radius_km=10.0) == []


def test_ranking_is_reproducible(service):
    candidates = [
        make_candidate(name=f"Clinic {i}", kind=KIND_CLINIC,
                       latitude=9.66 + i / 100, longitude=80.02, source_element_id=f"node/{i}")
        for i in range(6)
    ]
    args = dict(requested_kind=KIND_DOCTOR, requested_specialty="cardiology",
                origin_lat=9.6698, origin_lon=80.0206, radius_km=25.0)

    first = service.rank(candidates, **args)
    second = service.rank(list(reversed(candidates)), **args)

    assert [(r.candidate.name, r.match_score) for r in first] == [
        (r.candidate.name, r.match_score) for r in second
    ]


def test_scores_are_finite(service):
    ranked = service.rank([make_candidate()], KIND_HOSPITAL,
                          origin_lat=9.66, origin_lon=80.02, radius_km=10.0)
    assert math.isfinite(ranked[0].match_score)


# ----------------------------------------------------------------------
# Service accessor
# ----------------------------------------------------------------------


def test_accessor_returns_a_shared_instance():
    assert get_provider_discovery_service() is get_provider_discovery_service()


def test_service_performs_no_io():
    """
    The module must not import a database session, an HTTP client or the
    settings, so that this layer stays pure and offline-testable.
    """
    import app.services.provider_discovery_service as module

    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("import httpx", "from app.db", "get_db", "Session", "requests"):
        assert forbidden not in source, f"discovery service must not reference {forbidden}"
