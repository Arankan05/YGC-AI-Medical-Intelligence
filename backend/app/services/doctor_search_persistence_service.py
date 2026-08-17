"""
Persistence layer for Doctor Search & Healthcare Provider Recommendation.

Design principles:
- Separation of concerns: ProviderDiscoveryService decides what a provider is
  worth; this service decides how a search and its results are stored. The
  ranking itself stays pure and side-effect free.
- Reuses the existing DoctorSearch and DoctorRecommendation models. No new
  model, table, column or migration is introduced.
- Append-only: every search is a distinct event with its own timestamp, so a
  repeated search is recorded again rather than overwriting the earlier one.
  History is never pruned here.
- Scores are not stored. match_score and match_breakdown are recomputed from
  persisted fields on every read, so a stored search re-reads at the identical
  score it was created with.
- Tenant-safe: patient_id is supplied by the API layer after authentication and
  is applied to every row written. DoctorRecommendation carries no patient of
  its own, so every read of it is joined through DoctorSearch.patient_id.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.doctor_recommendation import DoctorRecommendation
from app.models.doctor_search import DoctorSearch
from app.models.finding import Finding
from app.services.provider_discovery_service import (
    MatchBreakdown,
    ProviderCandidate,
    ProviderDiscoveryService,
    RankedProvider,
    get_provider_discovery_service,
)

logger = logging.getLogger(__name__)

# Column limits from the DoctorSearch / DoctorRecommendation models, applied
# defensively so an unusually long value from an open data source can never
# overflow a column on PostgreSQL.
_LOCATION_QUERY_MAX_LENGTH = 255
_SPECIALTY_MAX_LENGTH = 100
_PROVIDER_NAME_MAX_LENGTH = 255
_PHONE_MAX_LENGTH = 50
_WEBSITE_MAX_LENGTH = 500

# Recorded on every recommendation so a reader knows which open data source a
# provider came from without inferring it from the shape of the record.
DEFAULT_SOURCE = "openstreetmap"


@dataclass(frozen=True)
class ScoredRecommendation:
    """
    A stored recommendation together with everything derived from it on read.

    `kind` and `specialties` are decoded from the recommendation's scope, and
    the score is recomputed. None of these three is stored.
    """

    recommendation: DoctorRecommendation
    kind: Optional[str]
    specialties: Tuple[str, ...]
    match_score: float
    match_breakdown: MatchBreakdown


def _truncate(value: Optional[str], limit: int) -> Optional[str]:
    """Trims to the column limit, preserving None so absence stays absence."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


class DoctorSearchPersistenceService:
    """
    Writes and reads provider searches for one patient.

    The patient identifier is never discovered here. It arrives already resolved
    from the authenticated user and is applied to every write and every read.
    """

    def __init__(self, discovery: Optional[ProviderDiscoveryService] = None) -> None:
        self._discovery = discovery or get_provider_discovery_service()

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def record_search(
        self,
        db: Session,
        *,
        patient_id: UUID,
        location_query: str,
        requested_kind: str,
        requested_specialty: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        search_radius: Optional[float] = None,
        availability_preference: Optional[str] = None,
        finding_id: Optional[UUID] = None,
        ranked: Sequence[RankedProvider] = (),
    ) -> DoctorSearch:
        """
        Records one search and its ranked results.

        A new DoctorSearch row is always created: searching the same place twice
        is two events, and collapsing them would erase the history the search
        list exists to show.

        `requested_kind` and `requested_specialty` are encoded into the search's
        scope. Each result stores its own scope, built from what that provider
        actually publishes - a requested specialty the provider does not publish
        is never written onto it.

        Returns the persisted DoctorSearch with its recommendations attached.
        """
        scope = self._discovery.build_search_scope(requested_kind, requested_specialty)

        search = DoctorSearch(
            patient_id=patient_id,
            finding_id=self._safe_finding_id(db, patient_id, finding_id),
            specialty=_truncate(scope, _SPECIALTY_MAX_LENGTH) or requested_kind,
            location_query=_truncate(location_query, _LOCATION_QUERY_MAX_LENGTH) or "",
            latitude=latitude,
            longitude=longitude,
            availability_preference=_truncate(availability_preference, _SPECIALTY_MAX_LENGTH),
            search_radius=search_radius,
        )
        db.add(search)
        db.flush()  # assigns search.id without ending the transaction

        for item in ranked:
            recommendation = self._build_recommendation(search.id, item)
            if recommendation is not None:
                db.add(recommendation)

        db.commit()
        db.refresh(search)
        return search

    def _build_recommendation(
        self,
        search_id: UUID,
        ranked: RankedProvider,
    ) -> Optional[DoctorRecommendation]:
        """
        Converts one ranked provider into a row.

        Returns None for a candidate with no usable name, because provider_name
        is NOT NULL and a placeholder name would be our invention rather than
        the source's data.
        """
        candidate = ranked.candidate

        provider_name = _truncate(candidate.name, _PROVIDER_NAME_MAX_LENGTH)
        if provider_name is None:
            logger.warning("Skipping a provider with no published name.")
            return None

        # Only a specialty the provider itself publishes is recorded. Where it
        # publishes several, the first is kept: the column holds one, and
        # picking the first keeps the choice deterministic.
        published_specialty = candidate.specialties[0] if candidate.specialties else None
        scope = self._discovery.build_search_scope(candidate.kind, published_specialty)

        return DoctorRecommendation(
            doctor_search_id=search_id,
            provider_name=provider_name,
            specialty=_truncate(scope, _SPECIALTY_MAX_LENGTH) or candidate.kind,
            address=_clean_optional(candidate.address),
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            distance_km=ranked.distance_km,
            phone=_truncate(candidate.phone, _PHONE_MAX_LENGTH),
            website=_truncate(candidate.website, _WEBSITE_MAX_LENGTH),
            opening_hours=_clean_optional(candidate.opening_hours),
            source=_truncate(candidate.source, _SPECIALTY_MAX_LENGTH) or DEFAULT_SOURCE,
        )

    def _safe_finding_id(
        self,
        db: Session,
        patient_id: UUID,
        finding_id: Optional[UUID],
    ) -> Optional[UUID]:
        """
        Links a finding only when it belongs to this patient.

        The API layer checks ownership before calling, so a mismatch here means
        a bug or a probe. The search is still recorded - it is a legitimate
        search - but it is left unlinked rather than pointing at another
        patient's finding, and the mismatch is logged.
        """
        if finding_id is None:
            return None

        owned = (
            db.query(Finding.id)
            .filter(Finding.id == finding_id, Finding.patient_id == patient_id)
            .first()
        )
        if owned is None:
            logger.warning(
                "Refusing to link finding %s to a search for a different patient.",
                finding_id,
            )
            return None
        return finding_id

    # ------------------------------------------------------------------
    # Reading - always scoped to the patient
    # ------------------------------------------------------------------

    def list_searches(
        self,
        db: Session,
        *,
        patient_id: UUID,
        limit: Optional[int] = None,
    ) -> List[DoctorSearch]:
        """Returns this patient's searches, most recent first."""
        query = (
            db.query(DoctorSearch)
            .filter(DoctorSearch.patient_id == patient_id)
            .order_by(DoctorSearch.created_at.desc(), DoctorSearch.id.desc())
        )
        if limit is not None and limit > 0:
            query = query.limit(limit)
        return query.all()

    def list_searches_with_counts(
        self,
        db: Session,
        *,
        patient_id: UUID,
        limit: Optional[int] = None,
    ) -> List[Tuple[DoctorSearch, int]]:
        """
        Returns this patient's searches paired with how many results each holds,
        most recent first.

        The count is aggregated in one grouped query rather than a count per
        search, so listing a long history stays a single round trip. The outer
        join keeps searches that found nothing, which are meaningful history.
        """
        query = (
            db.query(DoctorSearch, func.count(DoctorRecommendation.id))
            .outerjoin(
                DoctorRecommendation,
                DoctorRecommendation.doctor_search_id == DoctorSearch.id,
            )
            .filter(DoctorSearch.patient_id == patient_id)
            .group_by(DoctorSearch.id)
            .order_by(DoctorSearch.created_at.desc(), DoctorSearch.id.desc())
        )
        if limit is not None and limit > 0:
            query = query.limit(limit)
        return [(search, int(count or 0)) for search, count in query.all()]

    def get_search(
        self,
        db: Session,
        *,
        patient_id: UUID,
        search_id: UUID,
    ) -> Optional[DoctorSearch]:
        """
        Returns one search belonging to this patient, or None.

        None means "not this patient's", whether the row belongs to someone else
        or does not exist. The two are deliberately indistinguishable to the
        caller so a 404 cannot be used to probe for other patients' search ids.
        """
        return (
            db.query(DoctorSearch)
            .options(joinedload(DoctorSearch.recommendations))
            .filter(DoctorSearch.id == search_id, DoctorSearch.patient_id == patient_id)
            .first()
        )

    def list_recommendations(
        self,
        db: Session,
        *,
        patient_id: UUID,
        search_id: UUID,
    ) -> List[DoctorRecommendation]:
        """
        Returns the recommendations for one of this patient's searches.

        DoctorRecommendation has no patient of its own, so the patient filter is
        applied by joining DoctorSearch. Querying the recommendations table
        without this join would return every patient's providers.
        """
        return (
            db.query(DoctorRecommendation)
            .join(DoctorSearch, DoctorRecommendation.doctor_search_id == DoctorSearch.id)
            .filter(
                DoctorSearch.patient_id == patient_id,
                DoctorSearch.id == search_id,
            )
            .all()
        )

    def count_recommendations(
        self,
        db: Session,
        *,
        patient_id: UUID,
        search_id: UUID,
    ) -> int:
        """Counts one search's results, scoped through the owning search."""
        return (
            db.query(DoctorRecommendation)
            .join(DoctorSearch, DoctorRecommendation.doctor_search_id == DoctorSearch.id)
            .filter(
                DoctorSearch.patient_id == patient_id,
                DoctorSearch.id == search_id,
            )
            .count()
        )

    # ------------------------------------------------------------------
    # Re-deriving what was deliberately not stored
    # ------------------------------------------------------------------

    def to_candidate(self, recommendation: DoctorRecommendation) -> ProviderCandidate:
        """
        Rebuilds a candidate from a stored row so it can be re-scored.

        An unreadable scope yields an empty kind, which scores zero rather than
        being guessed at.
        """
        kind, specialties = self._discovery.parse_search_scope(recommendation.specialty)
        return ProviderCandidate(
            name=recommendation.provider_name or "",
            kind=kind or "",
            latitude=recommendation.latitude,
            longitude=recommendation.longitude,
            address=recommendation.address,
            phone=recommendation.phone,
            website=recommendation.website,
            opening_hours=recommendation.opening_hours,
            specialties=specialties,
            source=recommendation.source or DEFAULT_SOURCE,
            source_element_id=None,
        )

    def score_recommendations(
        self,
        search: DoctorSearch,
        recommendations: Sequence[DoctorRecommendation],
    ) -> List[ScoredRecommendation]:
        """
        Recomputes every score for a stored search and orders them best first.

        Each input is a persisted value - the search's scope, radius and
        availability preference, and the recommendation's own fields - so this
        reproduces the ranking the patient originally saw. Ties break on
        distance then name, matching ProviderDiscoveryService.rank.
        """
        requested_kind, requested_specialties = self._discovery.parse_search_scope(search.specialty)
        requested_specialty = requested_specialties[0] if requested_specialties else None

        scored: List[ScoredRecommendation] = []
        for recommendation in recommendations:
            candidate = self.to_candidate(recommendation)
            breakdown = self._discovery.score(
                candidate=candidate,
                requested_kind=requested_kind or "",
                requested_specialty=requested_specialty,
                distance_km=recommendation.distance_km,
                radius_km=search.search_radius,
                availability_preference=search.availability_preference,
            )
            scored.append(
                ScoredRecommendation(
                    recommendation=recommendation,
                    kind=candidate.kind or None,
                    specialties=candidate.specialties,
                    match_score=breakdown.total,
                    match_breakdown=breakdown,
                )
            )

        scored.sort(
            key=lambda item: (
                -item.match_score,
                item.recommendation.distance_km
                if item.recommendation.distance_km is not None
                else math.inf,
                (item.recommendation.provider_name or "").lower(),
            )
        )
        return scored

    def load_scored_search(
        self,
        db: Session,
        *,
        patient_id: UUID,
        search_id: UUID,
    ) -> Optional[Tuple[DoctorSearch, List[ScoredRecommendation]]]:
        """
        Loads one of this patient's searches with its results re-scored and
        ordered, or None when the search is not theirs.
        """
        search = self.get_search(db, patient_id=patient_id, search_id=search_id)
        if search is None:
            return None
        return search, self.score_recommendations(search, list(search.recommendations))


def _clean_optional(value: Optional[str]) -> Optional[str]:
    """Trims unbounded text, preserving None so absence stays absence."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_default_doctor_search_persistence_service: Optional[DoctorSearchPersistenceService] = None


def get_doctor_search_persistence_service() -> DoctorSearchPersistenceService:
    """Return the shared DoctorSearchPersistenceService instance."""

    global _default_doctor_search_persistence_service

    if _default_doctor_search_persistence_service is None:
        _default_doctor_search_persistence_service = DoctorSearchPersistenceService()

    return _default_doctor_search_persistence_service
