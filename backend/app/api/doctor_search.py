import logging
from typing import List, Optional, Sequence, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.records import get_patient_for_user
from app.core.security import get_current_application_user
from app.db.database import get_db
from app.models.doctor_search import DoctorSearch
from app.models.finding import Finding
from app.models.user import User
from app.schemas.doctor_search import (
    DoctorRecommendationResponse,
    DoctorSearchHistoryResponse,
    DoctorSearchResponse,
    DoctorSearchSummaryResponse,
    ProviderMatchBreakdownResponse,
    ProviderSearchRequest,
)
from app.services.doctor_search_persistence_service import (
    DoctorSearchPersistenceService,
    ScoredRecommendation,
    get_doctor_search_persistence_service,
)
from app.services.geocoding_service import GeocodingService, get_geocoding_service
from app.services.overpass_service import OverpassService, get_overpass_service
from app.services.provider_directory_errors import (
    DirectoryUnavailableError,
    LocationNotFoundError,
)
from app.services.provider_discovery_service import (
    KIND_DOCTOR,
    KIND_HOSPITAL,
    ProviderDiscoveryService,
    get_provider_discovery_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/doctor-search", tags=["doctor_search"])

# Upper bound on how much history one request will return.
_MAX_HISTORY_LIMIT = 100


# ----------------------------------------------------------------------
# Dependencies
#
# The two services that reach the public internet are injected rather than
# constructed inline, so tests can substitute them and never open a socket.
# ----------------------------------------------------------------------


def get_geocoder() -> GeocodingService:
    return get_geocoding_service()


def get_directory() -> OverpassService:
    return get_overpass_service()


def get_discovery() -> ProviderDiscoveryService:
    return get_provider_discovery_service()


def get_persistence() -> DoctorSearchPersistenceService:
    return get_doctor_search_persistence_service()


# ----------------------------------------------------------------------
# Response mapping
# ----------------------------------------------------------------------


def _map_breakdown(scored: ScoredRecommendation) -> ProviderMatchBreakdownResponse:
    return ProviderMatchBreakdownResponse(
        specialty=scored.match_breakdown.specialty,
        distance=scored.match_breakdown.distance,
        completeness=scored.match_breakdown.completeness,
        verified=scored.match_breakdown.verified,
    )


def _map_recommendation(scored: ScoredRecommendation) -> DoctorRecommendationResponse:
    """
    Converts a scored recommendation into its public form.

    The stored scope is not exposed: `kind` and `specialties` are its decoded
    parts, and the encoding itself is an internal storage detail. The score and
    its breakdown are the values recomputed on this read.
    """
    recommendation = scored.recommendation
    return DoctorRecommendationResponse(
        id=recommendation.id,
        provider_name=recommendation.provider_name,
        kind=scored.kind or "",
        specialties=list(scored.specialties),
        address=recommendation.address,
        latitude=recommendation.latitude,
        longitude=recommendation.longitude,
        distance_km=recommendation.distance_km,
        phone=recommendation.phone,
        website=recommendation.website,
        opening_hours=recommendation.opening_hours,
        source=recommendation.source,
        match_score=scored.match_score,
        match_breakdown=_map_breakdown(scored),
        created_at=recommendation.created_at,
    )


def _map_summary(search: DoctorSearch, result_count: int) -> DoctorSearchSummaryResponse:
    """
    Converts a search into its public form.

    The patient identifier is deliberately not exposed; the caller is already
    scoped to their own patient record by the endpoint. `specialty` carries the
    stored scope verbatim ("hospital", "doctor:cardiology").
    """
    return DoctorSearchSummaryResponse(
        id=search.id,
        specialty=search.specialty,
        location_query=search.location_query,
        latitude=search.latitude,
        longitude=search.longitude,
        availability_preference=search.availability_preference,
        search_radius=search.search_radius,
        finding_id=search.finding_id,
        result_count=result_count,
        created_at=search.created_at,
    )


def _map_search(
    search: DoctorSearch,
    scored: Sequence[ScoredRecommendation],
) -> DoctorSearchResponse:
    return DoctorSearchResponse(
        search=_map_summary(search, len(scored)),
        recommendations=[_map_recommendation(item) for item in scored],
    )


# ----------------------------------------------------------------------
# Search planning
# ----------------------------------------------------------------------


def _resolve_finding(
    db: Session,
    patient_id: UUID,
    finding_id: Optional[UUID],
) -> Optional[Finding]:
    """
    Loads a finding that belongs to this patient.

    A finding belonging to someone else is reported as not found, identically to
    one that does not exist, so the response cannot be used to discover whether
    another patient's finding id is real.
    """
    if finding_id is None:
        return None

    finding = (
        db.query(Finding)
        .filter(Finding.id == finding_id, Finding.patient_id == patient_id)
        .first()
    )
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found.",
        )
    return finding


def _plan_search(
    payload: ProviderSearchRequest,
    finding: Optional[Finding],
    discovery: ProviderDiscoveryService,
) -> Tuple[str, Optional[str], Optional[List[str]]]:
    """
    Decides what to search for.

    A specialty stated on the request wins; otherwise one may be derived from
    the finding that prompted the search. When no specialty is established the
    search is for hospitals, which is the honest fallback - it does not guess at
    a specialism the records do not support.

    Returns the scope's category, its specialty, and the categories to query.
    """
    specialty = payload.specialty
    if specialty is None and finding is not None:
        specialty = discovery.derive_specialty(
            finding_type=finding.finding_type,
            title=finding.title,
            description=finding.description,
        )

    if payload.kinds:
        # An explicit choice is authoritative; the first is the scope's category.
        return payload.kinds[0], specialty, list(payload.kinds)

    requested_kind = KIND_DOCTOR if specialty else KIND_HOSPITAL
    return requested_kind, specialty, None


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------


@router.post(
    "/search",
    response_model=DoctorSearchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Search for healthcare providers and record the search",
    description=(
        "Resolves the supplied place name to coordinates, queries OpenStreetMap for healthcare "
        "facilities within the radius, ranks them, and records the search together with its results "
        "for the authenticated patient. "
        "Every provider detail comes from the open data source: a detail the source did not publish "
        "is returned as null rather than filled in, and opening hours are passed through verbatim "
        "and never interpreted as appointment availability. "
        "An empty result list means the source returned no facilities for these criteria; it is a "
        "real answer about the area and is never padded with placeholder providers. "
        "The search location is saved as part of the patient's provider-search history."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "The place name could not be resolved, or the referenced finding does not belong to this patient",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The geocoding or healthcare directory service could not be reached",
        },
    },
)
def search_providers(
    payload: ProviderSearchRequest,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    geocoder: GeocodingService = Depends(get_geocoder),
    directory: OverpassService = Depends(get_directory),
    discovery: ProviderDiscoveryService = Depends(get_discovery),
    persistence: DoctorSearchPersistenceService = Depends(get_persistence),
) -> DoctorSearchResponse:
    patient = get_patient_for_user(current_user, db)
    finding = _resolve_finding(db, patient.id, payload.finding_id)
    requested_kind, specialty, query_kinds = _plan_search(payload, finding, discovery)

    try:
        located = geocoder.geocode(payload.location)
    except LocationNotFoundError:
        # The geocoder answered and recognised no such place. That is a correct
        # negative answer, not an outage, so it must not be reported as one.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="We could not find that location. Try a nearby town or a different spelling.",
        )
    except DirectoryUnavailableError as exc:
        logger.warning("Geocoding unavailable (%s): %s", exc.service, exc.cause)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The location service is temporarily unavailable. Please try again shortly.",
        )

    try:
        raw_payload = directory.fetch_healthcare_facilities(
            latitude=located.latitude,
            longitude=located.longitude,
            radius_km=payload.radius_km,
            kinds=query_kinds,
        )
    except DirectoryUnavailableError as exc:
        logger.warning("Provider directory unavailable (%s): %s", exc.service, exc.cause)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The healthcare directory is temporarily unavailable. Please try again shortly.",
        )

    candidates = discovery.parse_overpass_response(raw_payload)
    ranked = discovery.rank(
        candidates=candidates,
        requested_kind=requested_kind,
        requested_specialty=specialty,
        origin_lat=located.latitude,
        origin_lon=located.longitude,
        radius_km=payload.radius_km,
        availability_preference=payload.availability,
    )

    search = persistence.record_search(
        db,
        patient_id=patient.id,
        location_query=payload.location,
        requested_kind=requested_kind,
        requested_specialty=specialty,
        latitude=located.latitude,
        longitude=located.longitude,
        search_radius=payload.radius_km,
        availability_preference=payload.availability,
        finding_id=finding.id if finding is not None else None,
        ranked=ranked,
    )

    scored = persistence.score_recommendations(search, list(search.recommendations))
    return _map_search(search, scored)


@router.get(
    "/history",
    response_model=DoctorSearchHistoryResponse,
    summary="List the authenticated patient's previous provider searches",
    description=(
        "Returns the provider searches recorded for the authenticated patient, most recent first, "
        "with the number of providers each one found. Searches that found nothing are included, "
        "because an empty result is itself part of the history. Only this patient's searches are "
        "ever returned."
    ),
)
def list_search_history(
    limit: int = Query(
        default=20,
        ge=1,
        le=_MAX_HISTORY_LIMIT,
        description="Maximum number of searches to return",
    ),
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    persistence: DoctorSearchPersistenceService = Depends(get_persistence),
) -> DoctorSearchHistoryResponse:
    patient = get_patient_for_user(current_user, db)
    rows = persistence.list_searches_with_counts(db, patient_id=patient.id, limit=limit)
    return DoctorSearchHistoryResponse(
        searches=[_map_summary(search, count) for search, count in rows],
    )


@router.get(
    "/searches/{search_id}",
    response_model=DoctorSearchResponse,
    summary="Get one recorded provider search with its ranked results",
    description=(
        "Returns a previously recorded search belonging to the authenticated patient, together with "
        "its providers re-ranked. Scores are recomputed from the stored fields rather than read back, "
        "so a saved search reproduces the ranking it was created with. "
        "Responds with HTTP 404 when the search does not belong to this patient, whether it belongs "
        "to another patient or does not exist."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "No such search for the authenticated patient",
        },
    },
)
def get_recorded_search(
    search_id: UUID,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    persistence: DoctorSearchPersistenceService = Depends(get_persistence),
) -> DoctorSearchResponse:
    patient = get_patient_for_user(current_user, db)
    loaded = persistence.load_scored_search(
        db,
        patient_id=patient.id,
        search_id=search_id,
    )

    # The lookup is already filtered by patient_id, so a miss means this patient
    # has no such search. Another patient holding that id cannot satisfy it.
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider search not found.",
        )

    search, scored = loaded
    return _map_search(search, scored)
