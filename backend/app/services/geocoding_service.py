"""
Geocoding of free-text place names via OpenStreetMap Nominatim.

The service:
- Performs exactly one kind of I/O: an HTTP GET to the configured Nominatim
  instance. It holds no database session and writes nothing.
- Never invents coordinates. If the geocoder is unreachable the caller gets an
  outage error; if the geocoder recognises no such place the caller gets a
  not-found error. Neither is ever answered with a plausible-looking guess.
- Reports what the place name actually resolved to. Nominatim ranks several
  candidates and "Jaffna" is not unambiguous, so the resolved display name and
  the number of candidates come back with the coordinates and can be shown to
  the patient rather than silently assumed.
- Honours the Nominatim usage policy: a descriptive User-Agent identifying this
  application, an explicit timeout, and at most one request per second.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

import httpx

from app.core.config import get_settings
from app.services.provider_directory_agent import build_user_agent
from app.services.provider_directory_errors import (
    GeocodingUnavailableError,
    LocationNotFoundError,
)

logger = logging.getLogger(__name__)

# The policy also asks for no more than one request per second per application.
_MIN_REQUEST_INTERVAL_SECONDS = 1.0

# Nominatim is usually fast. A request that has not answered within these
# bounds is treated as an outage rather than waited on, so a patient is not
# left watching a spinner for a service that is not coming back.
_CONNECT_TIMEOUT_SECONDS = 5.0
_READ_TIMEOUT_SECONDS = 10.0

# More than one candidate is worth reporting as ambiguity; there is no value in
# fetching a long tail of them.
_CANDIDATE_LIMIT = 5


# Default country code restriction for Sri Lankan healthcare intelligence.
_DEFAULT_COUNTRY_CODES = "lk"


@dataclass(frozen=True)
class GeocodedLocation:
    """
    A place name resolved to coordinates.

    `display_name` is the geocoder's own description of what it matched, and
    `candidate_count` is how many places it considered. Together they let the
    caller show what was actually searched instead of implying the patient's
    text was matched exactly.
    """

    query: str
    display_name: str
    latitude: float
    longitude: float
    candidate_count: int


@dataclass(frozen=True)
class _ParsedCandidate:
    display_name: str
    latitude: float
    longitude: float
    is_sri_lanka: bool


class GeocodingService:
    """
    Resolves free-text place names to coordinates via Nominatim.

    The rate-limit clock is per instance, so the shared instance returned by
    `get_geocoding_service()` paces the whole application. `sleep` and
    `monotonic` are injectable so tests can assert the pacing without waiting
    for it.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        min_request_interval: float = _MIN_REQUEST_INTERVAL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base_url = base_url
        self._user_agent = user_agent
        self._min_request_interval = min_request_interval
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request_at: Optional[float] = None

    def _resolve_user_agent(self) -> str:
        """
        Builds the identifying User-Agent, including the configured contact.

        Read per request rather than at construction so that changing the
        contact does not require rebuilding the shared service instance.
        """
        if self._user_agent:
            return self._user_agent
        return build_user_agent(get_settings().PROVIDER_DIRECTORY_CONTACT)

    def _resolve_base_url(self) -> str:
        """Falls back to the configured Nominatim instance when none was given."""
        base_url = self._base_url or get_settings().NOMINATIM_URL
        if not base_url or not str(base_url).strip():
            raise GeocodingUnavailableError(
                "No geocoding service is configured.",
                cause="NOMINATIM_URL is empty",
            )
        return str(base_url).strip().rstrip("/")

    def _throttle(self) -> None:
        """Waits out the remainder of the minimum interval since the last request."""
        if self._min_request_interval <= 0 or self._last_request_at is None:
            return
        elapsed = self._monotonic() - self._last_request_at
        remaining = self._min_request_interval - elapsed
        if remaining > 0:
            self._sleep(remaining)

    def geocode(
        self,
        location: str,
        *,
        client: Optional[httpx.Client] = None,
    ) -> GeocodedLocation:
        """
        Resolves a place name to coordinates.

        Raises:
            LocationNotFoundError: The geocoder answered and matched no place.
            GeocodingUnavailableError: The geocoder could not be reached, timed
                out, refused the request, or returned something unreadable.
        """
        query = (location or "").strip()
        if not query:
            raise LocationNotFoundError(location or "")

        url = f"{self._resolve_base_url()}/search"
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": str(_CANDIDATE_LIMIT),
            "addressdetails": "1",
            "countrycodes": _DEFAULT_COUNTRY_CODES,
        }

        payload = self._request(url, params, client)
        candidates = self._extract_candidates(query, payload)

        if not candidates and "sri lanka" not in query.lower():
            fallback_query = f"{query}, Sri Lanka"
            fallback_params = {
                "q": fallback_query,
                "format": "jsonv2",
                "limit": str(_CANDIDATE_LIMIT),
                "addressdetails": "1",
                "countrycodes": _DEFAULT_COUNTRY_CODES,
            }
            fallback_payload = self._request(url, fallback_params, client)
            candidates = self._extract_candidates(query, fallback_payload)

        if not candidates:
            raise LocationNotFoundError(query)

        return self._select_best_candidate(query, candidates)

    def _request(
        self,
        url: str,
        params: dict,
        client: Optional[httpx.Client],
    ) -> Any:
        """
        Issues the throttled GET and returns the decoded JSON body.

        Every transport-level and protocol-level failure is converted into a
        single outage error, so a caller never has to distinguish a DNS failure
        from a 503 to know that the answer is "we do not know".
        """
        owned_client: Optional[httpx.Client] = None
        if client is None:
            owned_client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT_SECONDS,
                    read=_READ_TIMEOUT_SECONDS,
                    write=_READ_TIMEOUT_SECONDS,
                    pool=_CONNECT_TIMEOUT_SECONDS,
                ),
                follow_redirects=True,
            )
            client = owned_client

        try:
            self._throttle()
            try:
                response = client.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": self._resolve_user_agent(),
                        "Accept": "application/json",
                    },
                )
            except httpx.TimeoutException as exc:
                logger.warning("Geocoding request timed out: %s", type(exc).__name__)
                raise GeocodingUnavailableError(
                    "The geocoding service did not respond in time.",
                    cause=type(exc).__name__,
                ) from exc
            except httpx.HTTPError as exc:
                logger.warning("Geocoding request failed: %s", type(exc).__name__)
                raise GeocodingUnavailableError(
                    "The geocoding service could not be reached.",
                    cause=type(exc).__name__,
                ) from exc
            finally:
                self._last_request_at = self._monotonic()

            if response.status_code >= 400:
                logger.warning("Geocoding service returned HTTP %s", response.status_code)
                raise GeocodingUnavailableError(
                    "The geocoding service rejected the request.",
                    cause=f"HTTP {response.status_code}",
                )

            try:
                return response.json()
            except ValueError as exc:
                logger.warning("Geocoding service returned a non-JSON body.")
                raise GeocodingUnavailableError(
                    "The geocoding service returned an unreadable response.",
                    cause="invalid JSON",
                ) from exc
        finally:
            if owned_client is not None:
                owned_client.close()

    def _extract_candidates(self, query: str, payload: Any) -> List[_ParsedCandidate]:
        """
        Extracts valid geographic candidates from Nominatim payload.

        Supports cities, towns, villages, hamlets, suburbs, neighbourhoods,
        localities, municipalities, and administrative areas.
        """
        if not isinstance(payload, list):
            raise GeocodingUnavailableError(
                "The geocoding service returned an unexpected response shape.",
                cause=f"expected list, got {type(payload).__name__}",
            )

        candidates: List[_ParsedCandidate] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            try:
                latitude = float(entry["lat"])
                longitude = float(entry["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
                continue

            display_name = str(entry.get("display_name") or query).strip() or query
            address = entry.get("address") if isinstance(entry.get("address"), dict) else {}
            country_code = str(address.get("country_code") or "").strip().lower()
            is_sri_lanka = (country_code == "lk") or ("sri lanka" in display_name.lower())

            candidates.append(
                _ParsedCandidate(
                    display_name=display_name,
                    latitude=latitude,
                    longitude=longitude,
                    is_sri_lanka=is_sri_lanka,
                )
            )

        return candidates

    def _select_best_candidate(
        self,
        query: str,
        candidates: List[_ParsedCandidate],
    ) -> GeocodedLocation:
        """
        Selects the best candidate, prioritizing Sri Lankan results while
        preserving Nominatim's ranking order.
        """
        if not candidates:
            raise LocationNotFoundError(query)

        sri_lankan = [c for c in candidates if c.is_sri_lanka]
        best = sri_lankan[0] if sri_lankan else candidates[0]

        if len(candidates) > 1:
            logger.info(
                "Geocoded %r to %r (%d candidates considered)",
                query,
                best.display_name,
                len(candidates),
            )

        return GeocodedLocation(
            query=query,
            display_name=best.display_name,
            latitude=best.latitude,
            longitude=best.longitude,
            candidate_count=len(candidates),
        )


_default_geocoding_service: Optional[GeocodingService] = None


def get_geocoding_service() -> GeocodingService:
    """
    Return the shared GeocodingService instance.

    Sharing one instance is what makes the one-request-per-second pacing apply
    across the application rather than per call site.
    """

    global _default_geocoding_service

    if _default_geocoding_service is None:
        _default_geocoding_service = GeocodingService()

    return _default_geocoding_service
