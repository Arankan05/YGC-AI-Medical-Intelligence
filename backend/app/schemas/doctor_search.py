"""
Public request and response schemas for Doctor Search & Healthcare Provider
Recommendation.

Design notes:
- Reuses the existing DoctorSearch and DoctorRecommendation models. No new
  provider table, column or migration is introduced by this contract.
- `match_score` and `match_breakdown` are DERIVED, not stored. They are
  recomputed deterministically by the discovery service from fields that are
  persisted (specialty, distance, contact completeness), so the same stored row
  always produces the same score. Because they are not ORM attributes, the API
  layer builds these responses explicitly rather than relying on
  `from_attributes` to populate them.
- The patient identifier is never part of this contract. It is not accepted on
  the request (the API layer resolves it from the authenticated user) and it is
  not exposed on any response (the caller is already scoped to their own
  patient record).
- Map marker placement is a presentation concern. Only latitude and longitude
  are returned; the frontend derives marker positions from them.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Facility categories this feature recognises, mirroring the OpenStreetMap
# healthcare tags that Overpass returns and the ProviderKind union already
# declared in the frontend types.
PROVIDER_KINDS = (
    "hospital",
    "clinic",
    "doctor",
    "pharmacy",
    "laboratory",
)

# Availability is a ranking preference only. It never filters results and is
# never turned into an appointment time: only opening hours published by the
# source data are ever shown.
AVAILABILITY_PREFERENCES = (
    "this-week",
    "evenings",
    "weekends",
    "flexible",
)

# Column limits from the DoctorSearch / DoctorRecommendation models, applied at
# the edge so an over-long free-text location can never overflow the column.
_LOCATION_QUERY_MAX_LENGTH = 255
_SPECIALTY_MAX_LENGTH = 100

# The radius choices offered by the provider search screen. Capped so a single
# request cannot ask the upstream Overpass API for an unbounded area.
_MIN_SEARCH_RADIUS_KM = 1.0
_MAX_SEARCH_RADIUS_KM = 50.0
_DEFAULT_SEARCH_RADIUS_KM = 10.0


class ProviderSearchRequest(BaseModel):
    """
    Public schema for a provider search submitted by an authenticated patient.

    The patient is deliberately absent: it is resolved from the authenticated
    application user in the API layer and is never read from the request body.

    Supports either a free-text place name ('location') or explicit GPS coordinates
    ('latitude' and 'longitude').

    There is intentionally no "open now" flag. Deciding whether a facility is
    currently open would mean interpreting the source opening-hours text, and
    this feature never converts published hours into availability claims.
    """

    location: Optional[str] = Field(
        default=None,
        max_length=_LOCATION_QUERY_MAX_LENGTH,
        description="Free-text place name to search near (city, town or area), stored as the search's location_query",
    )
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="GPS latitude in decimal degrees (-90 to 90) for coordinate-based search",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="GPS longitude in decimal degrees (-180 to 180) for coordinate-based search",
    )
    radius_km: float = Field(
        default=_DEFAULT_SEARCH_RADIUS_KM,
        ge=_MIN_SEARCH_RADIUS_KM,
        le=_MAX_SEARCH_RADIUS_KM,
        description="Search radius in kilometres (1-50)",
    )
    specialty: Optional[str] = Field(
        default=None,
        max_length=_SPECIALTY_MAX_LENGTH,
        description="Requested medical specialty; derived from the linked finding when omitted",
    )
    finding_id: Optional[UUID] = Field(
        default=None,
        description="Clinical finding that prompted this search, used to derive the specialty when one is not supplied",
    )
    availability: Optional[str] = Field(
        default=None,
        description="Consultation availability preference used for ranking only ('this-week', 'evenings', 'weekends' or 'flexible')",
    )
    kinds: Optional[List[str]] = Field(
        default=None,
        description="Optional facility categories to restrict the search to ('hospital', 'clinic', 'doctor', 'pharmacy', 'laboratory')",
    )

    @model_validator(mode="after")
    def _validate_location_or_coordinates(self) -> "ProviderSearchRequest":
        """
        Ensures that either a non-empty location string or both latitude and longitude are supplied.
        """
        has_location = bool(self.location and self.location.strip())
        has_lat = self.latitude is not None
        has_lon = self.longitude is not None

        if has_lat != has_lon:
            raise ValueError("Both latitude and longitude must be provided for coordinate search.")

        if not has_location and not has_lat:
            raise ValueError("Either location text or both latitude and longitude must be provided.")

        if has_location and self.location:
            self.location = self.location.strip()

        return self

    @field_validator("specialty")
    @classmethod
    def _validate_specialty(cls, value: Optional[str]) -> Optional[str]:
        """Treats a blank specialty as absent so it can be derived instead."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("availability")
    @classmethod
    def _validate_availability(cls, value: Optional[str]) -> Optional[str]:
        """
        Accepts only the known preferences.

        An unrecognised value is rejected rather than stored, so a preference
        that the ranking cannot actually apply never looks like it was honoured.
        """
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        if cleaned not in AVAILABILITY_PREFERENCES:
            raise ValueError(
                f"Availability must be one of: {', '.join(AVAILABILITY_PREFERENCES)}."
            )
        return cleaned

    @field_validator("kinds")
    @classmethod
    def _validate_kinds(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """
        Accepts only known facility categories, de-duplicated and order-preserved.

        An unrecognised category is rejected rather than silently dropped, so a
        caller is never told a filter applied when it did not.
        """
        if value is None:
            return None

        normalized: List[str] = []
        for item in value:
            cleaned = (item or "").strip().lower()
            if not cleaned:
                continue
            if cleaned not in PROVIDER_KINDS:
                raise ValueError(
                    f"Unknown provider kind '{item}'. Expected one of: {', '.join(PROVIDER_KINDS)}."
                )
            if cleaned not in normalized:
                normalized.append(cleaned)

        return normalized or None

    # extra="forbid" rejects an unexpected key outright instead of ignoring it.
    # It matches the "reject rather than silently drop" stance already taken for
    # availability and kinds, and makes an attempt to smuggle in a field this
    # schema deliberately omits - patient_id above all - fail loudly with a 422
    # rather than succeed while the value is quietly discarded.
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ProviderMatchBreakdownResponse(BaseModel):
    """
    Public schema for the components that make up a provider's match score.

    The four components sum to `match_score`. They are recomputed on every
    response from persisted fields and are never stored, so no migration is
    involved in changing how ranking is presented.
    """

    specialty: float = Field(
        ...,
        description="Points contributed by how well the provider matches the requested specialty",
    )
    distance: float = Field(
        ...,
        description="Points contributed by proximity to the resolved search location",
    )
    completeness: float = Field(
        ...,
        description="Points contributed by how much contact detail the source data published",
    )
    verified: float = Field(
        ...,
        description="Points contributed by other verified details present in the source data",
    )

    model_config = ConfigDict(from_attributes=True)


class DoctorRecommendationResponse(BaseModel):
    """
    Public schema for one recommended healthcare provider.

    Every factual field originates from the upstream open data source named in
    `source`. Nothing here is generated: a detail the source did not publish is
    returned as null so the client can label it as unavailable rather than
    display an invented value.
    """

    id: UUID = Field(..., description="Unique recommendation identifier")
    provider_name: str = Field(..., description="Provider or facility name as published by the source")
    kind: str = Field(
        ...,
        description="Facility category ('hospital', 'clinic', 'doctor', 'pharmacy' or 'laboratory')",
    )
    specialties: List[str] = Field(
        default_factory=list,
        description="Specialty labels for this provider; empty when the source published none",
    )
    address: Optional[str] = Field(default=None, description="Published street address, or null when unavailable")
    latitude: Optional[float] = Field(default=None, description="Provider latitude in decimal degrees")
    longitude: Optional[float] = Field(default=None, description="Provider longitude in decimal degrees")
    distance_km: Optional[float] = Field(
        default=None,
        description="Straight-line distance from the resolved search location, in kilometres",
    )
    phone: Optional[str] = Field(default=None, description="Published contact number, or null when unavailable")
    website: Optional[str] = Field(default=None, description="Published website, or null when unavailable")
    opening_hours: Optional[str] = Field(
        default=None,
        description="Opening hours exactly as published by the source; never interpreted as appointment availability",
    )
    source: str = Field(..., description="Open data source this provider came from (e.g. 'openstreetmap')")
    match_score: float = Field(
        ...,
        description="Overall ranking score from 0 to 100, computed at response time and not stored",
    )
    match_breakdown: ProviderMatchBreakdownResponse = Field(
        ...,
        description="The components that sum to match_score, computed at response time and not stored",
    )
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class DoctorSearchSummaryResponse(BaseModel):
    """
    Public schema for a recorded provider search, without its results.

    Used for search history, where the criteria and the number of providers
    found are shown but the individual providers are not re-listed.
    """

    id: UUID = Field(..., description="Unique search identifier")
    specialty: str = Field(..., description="Specialty this search looked for")
    location_query: str = Field(..., description="Place name the patient searched near")
    latitude: Optional[float] = Field(default=None, description="Latitude the place name resolved to")
    longitude: Optional[float] = Field(default=None, description="Longitude the place name resolved to")
    availability_preference: Optional[str] = Field(
        default=None,
        description="Availability preference applied to ranking, or null when none was given",
    )
    search_radius: Optional[float] = Field(default=None, description="Search radius in kilometres")
    finding_id: Optional[UUID] = Field(
        default=None,
        description="Finding that prompted this search; null when unlinked or when that finding was since deleted",
    )
    result_count: int = Field(default=0, description="Number of providers recorded for this search")
    created_at: datetime = Field(..., description="When the search was performed")

    model_config = ConfigDict(from_attributes=True)


class DoctorSearchResponse(BaseModel):
    """
    Public schema for a completed provider search and its ranked results.

    `recommendations` is ordered by descending match_score. An empty list means
    the source data returned no healthcare facilities for these criteria; it is
    never padded with placeholder providers.
    """

    search: DoctorSearchSummaryResponse = Field(..., description="The search criteria that produced these results")
    recommendations: List[DoctorRecommendationResponse] = Field(
        default_factory=list,
        description="Recommended providers, highest match score first",
    )

    model_config = ConfigDict(from_attributes=True)


class DoctorSearchHistoryResponse(BaseModel):
    """
    Public schema for the authenticated patient's provider search history.
    """

    searches: List[DoctorSearchSummaryResponse] = Field(
        default_factory=list,
        description="Previous provider searches for this patient, most recent first",
    )

    model_config = ConfigDict(from_attributes=True)
