"""
Healthcare facility lookup via the OpenStreetMap Overpass API.

The service:
- Performs exactly one kind of I/O: an HTTP POST of an Overpass QL query. It
  holds no database session and writes nothing.
- Returns the raw decoded payload. Turning elements into providers is the
  discovery service's job, which keeps that logic pure and offline-testable.
- Distinguishes an outage from an empty area. A query that succeeds and matches
  nothing returns a payload with no elements - a real answer about the
  patient's area. Only an unreachable or unreadable service raises.
- Never fabricates. There is no fallback list, no cached sample area and no
  synthetic facility anywhere in this module.
"""

import logging
from typing import Any, Iterable, Optional, Sequence, Tuple

import httpx

from app.core.config import get_settings
from app.services.provider_directory_agent import build_user_agent
from app.services.provider_directory_errors import ProviderLookupUnavailableError

logger = logging.getLogger(__name__)

# Overpass is a shared community service and is frequently slow under load. The
# read timeout is generous because a slow answer is still a real answer, but it
# is bounded so a patient is not left waiting indefinitely.
_CONNECT_TIMEOUT_SECONDS = 10.0
_READ_TIMEOUT_SECONDS = 60.0

# The server-side budget declared inside the query itself. Kept below the read
# timeout so Overpass returns its own timeout error, which is more informative
# than the connection being cut from this side.
_QUERY_TIMEOUT_SECONDS = 50

# Overpass caps how much it will return; this bounds a dense-city query.
_MAX_ELEMENTS = 200

_MAX_RADIUS_KM = 50.0

# Our facility categories expressed as the OpenStreetMap tags that carry them.
# A category is matched if either tag matches, because mappers use both.
_KIND_TAGS: dict = {
    "hospital": {"amenity": ("hospital",), "healthcare": ("hospital",)},
    "clinic": {"amenity": ("clinic",), "healthcare": ("clinic", "centre", "center")},
    "doctor": {"amenity": ("doctors",), "healthcare": ("doctor", "physician")},
    "pharmacy": {"amenity": ("pharmacy",), "healthcare": ("pharmacy",)},
    "laboratory": {"amenity": ("laboratory",), "healthcare": ("laboratory", "sample_collection")},
}

_DEFAULT_KINDS: Tuple[str, ...] = ("hospital", "clinic", "doctor")


class OverpassService:
    """
    Fetches healthcare facilities near a point from the Overpass API.

    Query construction is a pure method, so the generated Overpass QL can be
    asserted in tests without any network involvement.
    """

    def __init__(self, base_url: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        self._base_url = base_url
        self._user_agent = user_agent

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
        base_url = self._base_url or get_settings().OVERPASS_URL
        if not base_url or not str(base_url).strip():
            raise ProviderLookupUnavailableError(
                "No healthcare directory service is configured.",
                cause="OVERPASS_URL is empty",
            )
        return str(base_url).strip()

    def build_query(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        kinds: Optional[Sequence[str]] = None,
    ) -> str:
        """
        Builds the Overpass QL for healthcare facilities within a radius.

        Nodes, ways and relations are all queried because a hospital is
        typically mapped as a building outline rather than a point, and `out
        center` gives those a usable coordinate.
        """
        selected = self._normalize_kinds(kinds)
        radius_m = int(round(max(0.0, min(float(radius_km), _MAX_RADIUS_KM)) * 1000))
        around = f"(around:{radius_m},{latitude:.6f},{longitude:.6f})"

        clauses: list = []
        for tag_key in ("amenity", "healthcare"):
            values = sorted(
                {
                    value
                    for kind in selected
                    for value in _KIND_TAGS[kind].get(tag_key, ())
                }
            )
            if not values:
                continue
            selector = f'["{tag_key}"~"^({"|".join(values)})$"]'
            for element in ("node", "way", "relation"):
                clauses.append(f"  {element}{selector}{around};")

        body = "\n".join(clauses)
        return (
            f"[out:json][timeout:{_QUERY_TIMEOUT_SECONDS}];\n"
            f"(\n{body}\n);\n"
            f"out center {_MAX_ELEMENTS};"
        )

    def _normalize_kinds(self, kinds: Optional[Iterable[str]]) -> Tuple[str, ...]:
        """
        Keeps only categories this service knows how to query.

        Falls back to the clinical categories when nothing usable was asked for,
        so a search always queries something real rather than building an empty
        query that would look like "no providers exist here".
        """
        if not kinds:
            return _DEFAULT_KINDS

        selected = tuple(
            kind for kind in dict.fromkeys((k or "").strip().lower() for k in kinds)
            if kind in _KIND_TAGS
        )
        return selected or _DEFAULT_KINDS

    def fetch_healthcare_facilities(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        kinds: Optional[Sequence[str]] = None,
        *,
        client: Optional[httpx.Client] = None,
    ) -> Any:
        """
        Runs the query and returns the decoded Overpass payload.

        A successful response with no elements is returned as-is: that is a
        genuine "nothing here", and it is the caller's empty state, not an error.

        Raises:
            ProviderLookupUnavailableError: The directory could not be reached,
                timed out, refused the query, or returned something unreadable.
        """
        query = self.build_query(latitude, longitude, radius_km, kinds)
        url = self._resolve_base_url()

        owned_client: Optional[httpx.Client] = None
        if client is None:
            owned_client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT_SECONDS,
                    read=_READ_TIMEOUT_SECONDS,
                    write=_CONNECT_TIMEOUT_SECONDS,
                    pool=_CONNECT_TIMEOUT_SECONDS,
                ),
                follow_redirects=True,
            )
            client = owned_client

        try:
            try:
                response = client.post(
                    url,
                    content=query.encode("utf-8"),
                    headers={
                        "User-Agent": self._resolve_user_agent(),
                        "Accept": "application/json",
                        "Content-Type": "text/plain; charset=utf-8",
                    },
                )
            except httpx.TimeoutException as exc:
                logger.warning("Overpass request timed out: %s", type(exc).__name__)
                raise ProviderLookupUnavailableError(
                    "The healthcare directory did not respond in time.",
                    cause=type(exc).__name__,
                ) from exc
            except httpx.HTTPError as exc:
                logger.warning("Overpass request failed: %s", type(exc).__name__)
                raise ProviderLookupUnavailableError(
                    "The healthcare directory could not be reached.",
                    cause=type(exc).__name__,
                ) from exc

            if response.status_code >= 400:
                logger.warning("Overpass returned HTTP %s", response.status_code)
                raise ProviderLookupUnavailableError(
                    "The healthcare directory rejected the request."
                    if response.status_code < 500
                    else "The healthcare directory is temporarily unavailable.",
                    cause=f"HTTP {response.status_code}",
                )

            try:
                payload = response.json()
            except ValueError as exc:
                logger.warning("Overpass returned a non-JSON body.")
                raise ProviderLookupUnavailableError(
                    "The healthcare directory returned an unreadable response.",
                    cause="invalid JSON",
                ) from exc

            if not isinstance(payload, dict):
                raise ProviderLookupUnavailableError(
                    "The healthcare directory returned an unexpected response shape.",
                    cause=f"expected object, got {type(payload).__name__}",
                )

            # Overpass reports a server-side timeout inside a 200 response, so a
            # remark must be inspected rather than assumed to be informational.
            remark = payload.get("remark")
            if isinstance(remark, str) and any(
                token in remark.lower() for token in ("timed out", "timeout", "runtime error")
            ):
                logger.warning("Overpass reported a query error: %s", remark)
                raise ProviderLookupUnavailableError(
                    "The healthcare directory could not complete the search in time.",
                    cause=remark.strip()[:200],
                )

            return payload
        finally:
            if owned_client is not None:
                owned_client.close()


_default_overpass_service: Optional[OverpassService] = None


def get_overpass_service() -> OverpassService:
    """Return the shared OverpassService instance."""

    global _default_overpass_service

    if _default_overpass_service is None:
        _default_overpass_service = OverpassService()

    return _default_overpass_service
