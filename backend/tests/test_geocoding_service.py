"""
Tests for the Nominatim geocoding service.

Every request is served by an httpx.MockTransport, so no test in this file
opens a socket. The transport is used in preference to patching internals
because it exercises the real request the service builds - URL, query string
and headers included.
"""

import httpx
import pytest

from app.services.geocoding_service import (
    GeocodedLocation,
    GeocodingService,
    get_geocoding_service,
)
from app.services.provider_directory_agent import build_user_agent
from app.services.provider_directory_errors import (
    GeocodingUnavailableError,
    LocationNotFoundError,
    ProviderDirectoryError,
)

BASE_URL = "https://nominatim.example.org"

JAFFNA = {
    "lat": "9.6615",
    "lon": "80.0255",
    "display_name": "Jaffna, Northern Province, Sri Lanka",
}
JAFFNA_ALT = {
    "lat": "9.7000",
    "lon": "80.1000",
    "display_name": "Jaffna District, Northern Province, Sri Lanka",
}


def make_service(handler, **kwargs) -> tuple:
    """Builds a service plus a client whose transport is the given handler."""
    service = GeocodingService(
        base_url=BASE_URL,
        sleep=lambda _seconds: None,
        monotonic=kwargs.pop("monotonic", lambda: 0.0),
        **kwargs,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return service, client


def json_handler(payload, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)
    return handler


# ----------------------------------------------------------------------
# Successful resolution
# ----------------------------------------------------------------------


def test_resolves_a_place_name_to_coordinates():
    service, client = make_service(json_handler([JAFFNA]))
    with client:
        result = service.geocode("Jaffna", client=client)

    assert isinstance(result, GeocodedLocation)
    assert result.latitude == pytest.approx(9.6615)
    assert result.longitude == pytest.approx(80.0255)
    assert result.display_name == "Jaffna, Northern Province, Sri Lanka"
    assert result.query == "Jaffna"
    assert result.candidate_count == 1


def test_reports_ambiguity_via_candidate_count():
    service, client = make_service(json_handler([JAFFNA, JAFFNA_ALT]))
    with client:
        result = service.geocode("Jaffna", client=client)

    # The top-ranked candidate is used, but the caller can see it was not the
    # only one, so the UI can show what was actually searched.
    assert result.candidate_count == 2
    assert result.latitude == pytest.approx(9.6615)


def test_query_is_trimmed_before_sending():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["q"] = request.url.params.get("q")
        return httpx.Response(200, json=[JAFFNA])

    service, client = make_service(handler)
    with client:
        result = service.geocode("   Jaffna   ", client=client)

    assert seen["q"] == "Jaffna"
    assert result.query == "Jaffna"


def test_request_targets_the_search_endpoint_with_json_format_and_country_restrictions():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["path"] = request.url.path
        seen["format"] = request.url.params.get("format")
        seen["addressdetails"] = request.url.params.get("addressdetails")
        seen["countrycodes"] = request.url.params.get("countrycodes")
        return httpx.Response(200, json=[JAFFNA])

    service, client = make_service(handler)
    with client:
        service.geocode("Colombo", client=client)

    assert seen["path"] == "/search"
    assert seen["url"].startswith(BASE_URL)
    assert seen["format"] == "jsonv2"
    assert seen["addressdetails"] == "1"
    assert seen["countrycodes"] == "lk"


def test_sends_a_descriptive_user_agent():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("User-Agent")
        return httpx.Response(200, json=[JAFFNA])

    service, client = make_service(handler)
    with client:
        service.geocode("Jaffna", client=client)

    # The Nominatim usage policy requires an identifying User-Agent.
    assert "MediGuardianAI" in seen["ua"]
    assert "healthcare provider search" in seen["ua"]
    assert seen["ua"] != "python-httpx"


def test_user_agent_advertises_the_configured_contact():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("User-Agent")
        return httpx.Response(200, json=[JAFFNA])

    service = GeocodingService(
        base_url=BASE_URL,
        user_agent=build_user_agent("mailto:ops@example.org"),
        sleep=lambda _s: None,
        monotonic=lambda: 0.0,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        service.geocode("Jaffna", client=client)

    assert "+mailto:ops@example.org" in seen["ua"]


def test_user_agent_claims_no_contact_when_none_is_configured():
    """
    A contact that is not real would satisfy the policy in form while
    guaranteeing nobody could reach us, so none is advertised instead.
    """
    assert build_user_agent(None) == "MediGuardianAI/0.1 (patient healthcare provider search)"
    assert build_user_agent("   ") == build_user_agent(None)
    assert "+" not in build_user_agent(None)


def test_trailing_slash_on_the_base_url_does_not_double_up():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=[JAFFNA])

    service = GeocodingService(base_url=BASE_URL + "/", sleep=lambda _s: None, monotonic=lambda: 0.0)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        service.geocode("Jaffna", client=client)

    assert seen["path"] == "/search"


# ----------------------------------------------------------------------
# Candidate selection and Sri Lankan locations
# ----------------------------------------------------------------------


def test_resolves_small_village_successfully():
    tellippalai = {
        "lat": "9.7820",
        "lon": "80.0380",
        "display_name": "Tellippalai, Jaffna District, Northern Province, Sri Lanka",
        "address": {"village": "Tellippalai", "country_code": "lk"},
    }
    service, client = make_service(json_handler([tellippalai]))
    with client:
        result = service.geocode("Tellippalai", client=client)

    assert result.query == "Tellippalai"
    assert result.latitude == pytest.approx(9.7820)
    assert result.longitude == pytest.approx(80.0380)
    assert "Tellippalai" in result.display_name


def test_prefers_sri_lankan_candidate_over_foreign_name_collision():
    indian_nallur = {
        "lat": "11.0500",
        "lon": "77.3000",
        "display_name": "Nallur, Tiruppur, Tamil Nadu, India",
        "address": {"town": "Nallur", "country_code": "in"},
    }
    sri_lankan_nallur = {
        "lat": "9.6700",
        "lon": "80.0300",
        "display_name": "Nallur, Jaffna District, Northern Province, Sri Lanka",
        "address": {"suburb": "Nallur", "country_code": "lk"},
    }

    service, client = make_service(json_handler([indian_nallur, sri_lankan_nallur]))
    with client:
        result = service.geocode("Nallur", client=client)

    assert result.latitude == pytest.approx(9.6700)
    assert result.longitude == pytest.approx(80.0300)
    assert "Sri Lanka" in result.display_name
    assert result.candidate_count == 2


def test_preserves_ranking_order_among_multiple_sri_lankan_candidates():
    nallur_1 = {
        "lat": "9.6700",
        "lon": "80.0300",
        "display_name": "Nallur, Jaffna, Sri Lanka",
        "address": {"suburb": "Nallur", "country_code": "lk"},
    }
    nallur_2 = {
        "lat": "9.6800",
        "lon": "80.0400",
        "display_name": "Nallur South, Jaffna, Sri Lanka",
        "address": {"village": "Nallur South", "country_code": "lk"},
    }

    service, client = make_service(json_handler([nallur_1, nallur_2]))
    with client:
        result = service.geocode("Nallur", client=client)

    assert result.latitude == pytest.approx(9.6700)
    assert result.display_name == "Nallur, Jaffna, Sri Lanka"
    assert result.candidate_count == 2


# ----------------------------------------------------------------------
# Fallback queries
# ----------------------------------------------------------------------


def test_primary_query_empty_triggers_successful_fallback():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        q = request.url.params.get("q")
        if q == "Tellippalai":
            return httpx.Response(200, json=[])
        if q == "Tellippalai, Sri Lanka":
            return httpx.Response(
                200,
                json=[
                    {
                        "lat": "9.7820",
                        "lon": "80.0380",
                        "display_name": "Tellippalai, Northern Province, Sri Lanka",
                        "address": {"village": "Tellippalai", "country_code": "lk"},
                    }
                ],
            )
        return httpx.Response(200, json=[])

    service, client = make_service(handler)
    with client:
        result = service.geocode("Tellippalai", client=client)

    assert len(requests) == 2
    assert requests[0].url.params.get("q") == "Tellippalai"
    assert requests[1].url.params.get("q") == "Tellippalai, Sri Lanka"
    assert result.query == "Tellippalai"
    assert result.latitude == pytest.approx(9.7820)
    assert result.longitude == pytest.approx(80.0380)


def test_query_already_containing_sri_lanka_does_not_trigger_fallback():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[])

    service, client = make_service(handler)
    with client:
        with pytest.raises(LocationNotFoundError):
            service.geocode("Tellippalai, Sri Lanka", client=client)

    # Only 1 request should be made since "Sri Lanka" is already in the query.
    assert len(requests) == 1
    assert requests[0].url.params.get("q") == "Tellippalai, Sri Lanka"


def test_successful_primary_query_does_not_trigger_fallback():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[JAFFNA])

    service, client = make_service(handler)
    with client:
        result = service.geocode("Jaffna", client=client)

    assert len(requests) == 1
    assert result.latitude == pytest.approx(9.6615)


# ----------------------------------------------------------------------
# Not found vs unavailable
# ----------------------------------------------------------------------


def test_empty_result_is_not_found_not_an_outage():
    service, client = make_service(json_handler([]))
    with client:
        with pytest.raises(LocationNotFoundError) as excinfo:
            service.geocode("Atlantis", client=client)

    assert excinfo.value.location == "Atlantis"
    # A negative answer must not masquerade as a service problem.
    assert not isinstance(excinfo.value, GeocodingUnavailableError)


def test_blank_location_is_not_found_without_a_request():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=[JAFFNA])

    service, client = make_service(handler)
    with client:
        with pytest.raises(LocationNotFoundError):
            service.geocode("   ", client=client)

    assert calls == []


@pytest.mark.parametrize("status", [400, 403, 429, 500, 502, 503])
def test_error_statuses_are_reported_as_unavailable(status):
    service, client = make_service(json_handler({"error": "nope"}, status_code=status))
    with client:
        with pytest.raises(GeocodingUnavailableError) as excinfo:
            service.geocode("Jaffna", client=client)

    assert excinfo.value.service == "nominatim"
    assert str(status) in excinfo.value.cause


def test_timeout_is_reported_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    service, client = make_service(handler)
    with client:
        with pytest.raises(GeocodingUnavailableError) as excinfo:
            service.geocode("Jaffna", client=client)

    assert "ReadTimeout" in excinfo.value.cause


def test_connection_error_is_reported_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    service, client = make_service(handler)
    with client:
        with pytest.raises(GeocodingUnavailableError):
            service.geocode("Jaffna", client=client)


def test_non_json_body_is_reported_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    service, client = make_service(handler)
    with client:
        with pytest.raises(GeocodingUnavailableError) as excinfo:
            service.geocode("Jaffna", client=client)

    assert excinfo.value.cause == "invalid JSON"


def test_unexpected_json_shape_is_reported_as_unavailable():
    service, client = make_service(json_handler({"results": []}))
    with client:
        with pytest.raises(GeocodingUnavailableError):
            service.geocode("Jaffna", client=client)


def test_missing_configuration_is_reported_as_unavailable():
    service = GeocodingService(base_url="   ", sleep=lambda _s: None, monotonic=lambda: 0.0)
    with pytest.raises(GeocodingUnavailableError) as excinfo:
        service.geocode("Jaffna")

    assert "NOMINATIM_URL" in excinfo.value.cause


# ----------------------------------------------------------------------
# Never fabricate
# ----------------------------------------------------------------------


def test_unreadable_coordinates_are_skipped_not_repaired():
    payload = [
        {"lat": "not-a-number", "lon": "80.0", "display_name": "Broken"},
        JAFFNA,
    ]
    service, client = make_service(json_handler(payload))
    with client:
        result = service.geocode("Jaffna", client=client)

    assert result.display_name == JAFFNA["display_name"]
    assert result.candidate_count == 1


def test_out_of_range_coordinates_are_rejected():
    payload = [{"lat": "999", "lon": "80.0", "display_name": "Impossible"}]
    service, client = make_service(json_handler(payload))
    with client:
        with pytest.raises(LocationNotFoundError):
            service.geocode("Jaffna", client=client)


def test_all_candidates_unreadable_is_not_found_not_a_guess():
    payload = [{"display_name": "No coordinates at all"}, {"lat": None, "lon": None}]
    service, client = make_service(json_handler(payload))
    with client:
        with pytest.raises(LocationNotFoundError):
            service.geocode("Jaffna", client=client)


def test_missing_display_name_falls_back_to_the_query_not_an_invention():
    payload = [{"lat": "9.66", "lon": "80.02"}]
    service, client = make_service(json_handler(payload))
    with client:
        result = service.geocode("Jaffna", client=client)

    assert result.display_name == "Jaffna"


def test_non_dict_entries_are_skipped():
    service, client = make_service(json_handler(["nonsense", 42, JAFFNA]))
    with client:
        result = service.geocode("Jaffna", client=client)

    assert result.candidate_count == 1


# ----------------------------------------------------------------------
# Rate limiting
# ----------------------------------------------------------------------


class Clock:
    """
    A hand-advanced clock.

    Driving the clock by value rather than by a fixed sequence keeps these tests
    independent of how many times the service happens to read it.
    """

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_first_request_does_not_wait():
    slept = []
    service = GeocodingService(base_url=BASE_URL, sleep=slept.append, monotonic=Clock(100.0))
    client = httpx.Client(transport=httpx.MockTransport(json_handler([JAFFNA])))
    with client:
        service.geocode("Jaffna", client=client)

    assert slept == []


def test_second_request_waits_out_the_minimum_interval():
    slept = []
    clock = Clock(0.0)
    service = GeocodingService(base_url=BASE_URL, sleep=slept.append, monotonic=clock)
    client = httpx.Client(transport=httpx.MockTransport(json_handler([JAFFNA])))
    with client:
        service.geocode("Jaffna", client=client)
        clock.now = 0.2
        service.geocode("Colombo", client=client)

    # 0.2s of the 1.0s policy interval has elapsed, so 0.8s remains.
    assert len(slept) == 1
    assert slept[0] == pytest.approx(0.8)


def test_fallback_query_respects_throttling():
    slept = []
    clock = Clock(0.0)

    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("q")
        if q == "Tellippalai":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[JAFFNA])

    service = GeocodingService(base_url=BASE_URL, sleep=slept.append, monotonic=clock)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        service.geocode("Tellippalai", client=client)

    # Initial request at t=0 sets _last_request_at=0.0. Fallback request immediately
    # executes and waits out the full 1.0s minimum interval.
    assert len(slept) == 1
    assert slept[0] == pytest.approx(1.0)


def test_no_wait_once_the_interval_has_passed():
    slept = []
    clock = Clock(0.0)
    service = GeocodingService(base_url=BASE_URL, sleep=slept.append, monotonic=clock)
    client = httpx.Client(transport=httpx.MockTransport(json_handler([JAFFNA])))
    with client:
        service.geocode("Jaffna", client=client)
        clock.now = 5.0
        service.geocode("Colombo", client=client)

    assert slept == []


def test_a_failed_request_still_counts_towards_pacing():
    """A rejected request has still been sent, so it must not be a free pass."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    slept = []
    clock = Clock(0.0)
    service = GeocodingService(base_url=BASE_URL, sleep=slept.append, monotonic=clock)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client:
        with pytest.raises(GeocodingUnavailableError):
            service.geocode("Jaffna", client=client)
        clock.now = 0.1
        with pytest.raises(GeocodingUnavailableError):
            service.geocode("Colombo", client=client)

    assert len(slept) == 1
    assert slept[0] == pytest.approx(0.9)


# ----------------------------------------------------------------------
# Error taxonomy and accessor
# ----------------------------------------------------------------------


def test_errors_share_a_common_base():
    assert issubclass(GeocodingUnavailableError, ProviderDirectoryError)
    assert issubclass(LocationNotFoundError, ProviderDirectoryError)


def test_accessor_returns_a_shared_instance():
    assert get_geocoding_service() is get_geocoding_service()

