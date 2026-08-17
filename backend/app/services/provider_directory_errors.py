"""
Failure modes for the external healthcare-directory lookups.

The distinction that matters here is between "the upstream service could not be
reached" and "the upstream service answered, and the answer was empty". They
look similar in code and mean opposite things to a patient: the first is a
temporary outage to retry, the second is a real, correct answer about their
area. The provider screens already render them as two different states, so they
are two different exception types - and neither is ever resolved by inventing a
location or a provider.
"""


class ProviderDirectoryError(Exception):
    """Base class for every healthcare-directory lookup failure."""


class DirectoryUnavailableError(ProviderDirectoryError):
    """
    An upstream service could not be reached, timed out, or answered with
    something unusable.

    This means "we do not know", never "there is nothing there". Callers must
    surface it as a service problem rather than as an empty result set.
    """

    def __init__(self, message: str, *, service: str, cause: str = "") -> None:
        super().__init__(message)
        self.service = service
        self.cause = cause


class GeocodingUnavailableError(DirectoryUnavailableError):
    """The geocoder could not be reached or returned an unusable response."""

    def __init__(self, message: str, *, cause: str = "") -> None:
        super().__init__(message, service="nominatim", cause=cause)


class LocationNotFoundError(ProviderDirectoryError):
    """
    The geocoder worked and recognised no such place.

    This is a successful lookup with a negative answer, not an outage. The
    remedy is a different search term, not a retry.
    """

    def __init__(self, location: str) -> None:
        super().__init__(f"No location matched '{location}'.")
        self.location = location


class ProviderLookupUnavailableError(DirectoryUnavailableError):
    """The provider directory could not be reached or returned an unusable response."""

    def __init__(self, message: str, *, cause: str = "") -> None:
        super().__init__(message, service="overpass", cause=cause)
