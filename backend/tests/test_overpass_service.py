"""
Tests for the Overpass healthcare directory service.

Every request is served by an httpx.MockTransport, so no test in this file
opens a socket. Query construction is pure and is asserted directly.
"""

import httpx
import pytest

from app.services.overpass_service import OverpassService, get_overpass_service
from app.services.provider_directory_agent import build_user_agent
from app.services.provider_directory_errors import (
    ProviderDirectoryError,
    ProviderLookupUnavailableError,
)

BASE_URL = "https://overpass.example.org/api/interpreter"

LAT, LON = 9.6615, 80.0255

HOSPITAL_ELEMENT = {
    "type": "node",
    "id": 1,
    "lat": 9.6698,
    "lon": 80.0206,
    "tags": {"amenity": "hospital", "name": "Jaffna Teaching Hospital"},
}


@pytest.fixture
def service() -> OverpassService:
    return OverpassService(base_url=BASE_URL)


def json_handler(payload, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)
    return handler


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ----------------------------------------------------------------------
# Query construction (pure - no HTTP)
# ----------------------------------------------------------------------


def test_query_declares_json_output_and_a_server_side_timeout(service):
    query = service.build_query(LAT, LON, 10.0)
    assert query.startswith("[out:json][timeout:")
    assert query.rstrip().endswith(";")


def test_query_converts_radius_to_metres(service):
    query = service.build_query(LAT, LON, 10.0)
    assert "(around:10000," in query


def test_query_includes_the_origin_coordinates(service):
    query = service.build_query(LAT, LON, 5.0)
    assert "9.661500" in query and "80.025500" in query


def test_query_covers_nodes_ways_and_relations(service):
    query = service.build_query(LAT, LON, 10.0)
    for element in ("node", "way", "relation"):
        assert f"  {element}[" in query


def test_query_requests_centres_so_building_outlines_have_coordinates(service):
    assert "out center" in service.build_query(LAT, LON, 10.0)


def test_query_matches_both_amenity_and_healthcare_tags(service):
    query = service.build_query(LAT, LON, 10.0)
    assert '["amenity"~' in query
    assert '["healthcare"~' in query


def test_query_defaults_to_clinical_categories(service):
    query = service.build_query(LAT, LON, 10.0)
    assert "hospital" in query and "clinic" in query and "doctors" in query
    # Pharmacies are not a default target for a clinical consultation search.
    assert "pharmacy" not in query


def test_query_honours_requested_kinds(service):
    query = service.build_query(LAT, LON, 10.0, kinds=["pharmacy"])
    assert "pharmacy" in query
    assert "doctors" not in query


def test_unknown_kinds_fall_back_to_the_defaults(service):
    query = service.build_query(LAT, LON, 10.0, kinds=["dentist", "florist"])
    assert "hospital" in query


def test_empty_kinds_fall_back_to_the_defaults(service):
    assert "hospital" in service.build_query(LAT, LON, 10.0, kinds=[])


def test_radius_is_capped(service):
    query = service.build_query(LAT, LON, 5000.0)
    assert "(around:50000," in query


def test_negative_radius_is_clamped_to_zero(service):
    assert "(around:0," in service.build_query(LAT, LON, -5.0)


def test_query_is_reproducible(service):
    assert service.build_query(LAT, LON, 10.0) == service.build_query(LAT, LON, 10.0)


def test_kind_order_does_not_change_the_query(service):
    a = service.build_query(LAT, LON, 10.0, kinds=["hospital", "clinic"])
    b = service.build_query(LAT, LON, 10.0, kinds=["clinic", "hospital"])
    assert a == b


# ----------------------------------------------------------------------
# Successful fetch
# ----------------------------------------------------------------------


def test_returns_the_decoded_payload(service):
    payload = {"elements": [HOSPITAL_ELEMENT]}
    with make_client(json_handler(payload)) as client:
        result = service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert result == payload


def test_empty_area_is_a_real_answer_not_an_error(service):
    with make_client(json_handler({"elements": []})) as client:
        result = service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    # No providers nearby is a correct answer about the patient's area.
    assert result["elements"] == []


def test_query_is_posted_as_the_request_body(service):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"elements": []})

    with make_client(handler) as client:
        service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert seen["method"] == "POST"
    assert seen["body"].startswith("[out:json]")
    assert "around:10000" in seen["body"]


def test_sends_a_descriptive_user_agent(service):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("User-Agent")
        return httpx.Response(200, json={"elements": []})

    with make_client(handler) as client:
        service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert "MediGuardianAI" in seen["ua"]
    assert "healthcare provider search" in seen["ua"]
    assert seen["ua"] != "python-httpx"


def test_user_agent_advertises_the_configured_contact():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("User-Agent")
        return httpx.Response(200, json={"elements": []})

    configured = OverpassService(
        base_url=BASE_URL, user_agent=build_user_agent("https://example.org/contact")
    )
    with make_client(handler) as client:
        configured.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert "+https://example.org/contact" in seen["ua"]


# ----------------------------------------------------------------------
# Failure handling - never fabricate
# ----------------------------------------------------------------------


@pytest.mark.parametrize("status", [400, 429, 500, 502, 503, 504])
def test_error_statuses_are_reported_as_unavailable(service, status):
    with make_client(json_handler({}, status_code=status)) as client:
        with pytest.raises(ProviderLookupUnavailableError) as excinfo:
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert excinfo.value.service == "overpass"
    assert str(status) in excinfo.value.cause


def test_server_errors_read_as_temporary(service):
    with make_client(json_handler({}, status_code=503)) as client:
        with pytest.raises(ProviderLookupUnavailableError) as excinfo:
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert "temporarily unavailable" in str(excinfo.value)


def test_timeout_is_reported_as_unavailable(service):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with make_client(handler) as client:
        with pytest.raises(ProviderLookupUnavailableError) as excinfo:
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert "ReadTimeout" in excinfo.value.cause


def test_connection_error_is_reported_as_unavailable(service):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    with make_client(handler) as client:
        with pytest.raises(ProviderLookupUnavailableError):
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)


def test_non_json_body_is_reported_as_unavailable(service):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Overpass is down for maintenance")

    with make_client(handler) as client:
        with pytest.raises(ProviderLookupUnavailableError) as excinfo:
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert excinfo.value.cause == "invalid JSON"


def test_unexpected_payload_shape_is_reported_as_unavailable(service):
    with make_client(json_handler([1, 2, 3])) as client:
        with pytest.raises(ProviderLookupUnavailableError):
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)


def test_server_side_timeout_inside_a_200_is_detected(service):
    """Overpass reports query timeouts in a remark on an otherwise-OK response."""
    payload = {"elements": [], "remark": "runtime error: Query timed out in 'query' at line 3"}
    with make_client(json_handler(payload)) as client:
        with pytest.raises(ProviderLookupUnavailableError) as excinfo:
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert "timed out" in excinfo.value.cause.lower()


def test_harmless_remark_does_not_fail_the_request(service):
    payload = {"elements": [HOSPITAL_ELEMENT], "remark": "considered 12 elements"}
    with make_client(json_handler(payload)) as client:
        result = service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    assert result["elements"] == [HOSPITAL_ELEMENT]


def test_missing_configuration_is_reported_as_unavailable():
    service = OverpassService(base_url="   ")
    with pytest.raises(ProviderLookupUnavailableError) as excinfo:
        service.fetch_healthcare_facilities(LAT, LON, 10.0)

    assert "OVERPASS_URL" in excinfo.value.cause


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(json_handler({}, status_code=500), id="server-error"),
        pytest.param(json_handler({}, status_code=429), id="rate-limited"),
        pytest.param(lambda r: (_ for _ in ()).throw(httpx.ConnectError("x", request=r)), id="unreachable"),
        pytest.param(lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("x", request=r)), id="timeout"),
        pytest.param(lambda r: httpx.Response(200, text="not json"), id="unreadable"),
        pytest.param(json_handler({"remark": "runtime error: Query timed out"}), id="query-timeout"),
    ],
)
def test_no_failure_mode_ever_returns_provider_data(service, handler):
    """
    A failure must never be softened into results. Every failure path raises;
    none of them returns a payload, an empty stand-in or sample data that a
    caller could mistake for a real answer about the patient's area.
    """
    with make_client(handler) as client:
        with pytest.raises(ProviderLookupUnavailableError):
            service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)


def test_module_holds_no_provider_records_to_fall_back_on(service):
    """
    The only module-level data is tag configuration. Nothing here contains a
    facility name, address, phone number or coordinate that could be served as
    a result when the upstream service is down.
    """
    import app.services.overpass_service as module

    for name, value in vars(module).items():
        if name.startswith("__") or not isinstance(value, (list, tuple, dict)):
            continue
        flattened = repr(value).lower()
        for provider_shaped in ("name", "addr", "phone", "lat", "lon"):
            assert provider_shaped not in flattened, (
                f"module constant {name} looks like it holds provider data"
            )


# ----------------------------------------------------------------------
# Error taxonomy and accessor
# ----------------------------------------------------------------------


def test_errors_share_a_common_base():
    assert issubclass(ProviderLookupUnavailableError, ProviderDirectoryError)


def test_accessor_returns_a_shared_instance():
    assert get_overpass_service() is get_overpass_service()


# ----------------------------------------------------------------------
# Integration with the pure parser (still no network)
# ----------------------------------------------------------------------


def test_fetched_payload_feeds_the_discovery_parser(service):
    """The two layers meet here: Overpass fetches, discovery interprets."""
    from app.services.provider_discovery_service import get_provider_discovery_service

    payload = {"elements": [HOSPITAL_ELEMENT]}
    with make_client(json_handler(payload)) as client:
        fetched = service.fetch_healthcare_facilities(LAT, LON, 10.0, client=client)

    candidates = get_provider_discovery_service().parse_overpass_response(fetched)
    assert [c.name for c in candidates] == ["Jaffna Teaching Hospital"]
    assert candidates[0].kind == "hospital"
