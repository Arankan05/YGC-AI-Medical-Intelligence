"""
Deterministic, side-effect free discovery and ranking logic for healthcare
providers.

The service:
- Performs no I/O. It neither opens a database session nor calls an external
  API. Raw payloads are handed to it; persistence and HTTP live elsewhere.
- Never invents a provider or a provider detail. A field the source did not
  publish stays None, and an element without a published name is discarded
  rather than given a placeholder one.
- Never interprets opening hours as availability. Published hours are carried
  through verbatim as text; nothing here decides whether a facility is open.
- Ranks reproducibly. Every scoring input is a value that is persisted, so
  re-scoring a stored recommendation later yields the identical score.
- Owns the search-scope encoding written to DoctorRecommendation.specialty, so
  the persistence layer and any reader share one definition.
"""

import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Facility categories, matching PROVIDER_KINDS in app.schemas.doctor_search and
# the ProviderKind union in the frontend types.
KIND_HOSPITAL = "hospital"
KIND_CLINIC = "clinic"
KIND_DOCTOR = "doctor"
KIND_PHARMACY = "pharmacy"
KIND_LABORATORY = "laboratory"

PROVIDER_KINDS: Tuple[str, ...] = (
    KIND_HOSPITAL,
    KIND_CLINIC,
    KIND_DOCTOR,
    KIND_PHARMACY,
    KIND_LABORATORY,
)

SOURCE_OPENSTREETMAP = "openstreetmap"

# Ranking weights. These are the weights the provider screens already state to
# the user, and they sum to 100.
SPECIALTY_WEIGHT = 40.0
DISTANCE_WEIGHT = 30.0
COMPLETENESS_WEIGHT = 15.0
VERIFIED_WEIGHT = 15.0

# Mean Earth radius (km), IUGG value, used for the great-circle distance.
_EARTH_RADIUS_KM = 6371.0088

# The scope string is written to DoctorRecommendation.specialty, a String(100)
# column. "laboratory" is the longest kind at 10 characters, so a specialty is
# capped so that "<kind>:<specialty>" can never overflow the column.
_SCOPE_MAX_LENGTH = 100
_SCOPE_SEPARATOR = ":"
_SPECIALTY_MAX_LENGTH = _SCOPE_MAX_LENGTH - max(len(k) for k in PROVIDER_KINDS) - len(_SCOPE_SEPARATOR)

# A normalized specialty is lowercase, hyphen-separated and free of anything
# that would make the encoded scope ambiguous to split.
_SPECIALTY_STRIP_PATTERN = re.compile(r"[^a-z0-9\-]+")
_SPECIALTY_COLLAPSE_PATTERN = re.compile(r"-{2,}")

# OpenStreetMap tags to facility categories. Both the amenity and healthcare
# keys are consulted because either may carry the classification.
_AMENITY_KIND: Dict[str, str] = {
    "hospital": KIND_HOSPITAL,
    "clinic": KIND_CLINIC,
    "doctors": KIND_DOCTOR,
    "pharmacy": KIND_PHARMACY,
    "laboratory": KIND_LABORATORY,
}

_HEALTHCARE_KIND: Dict[str, str] = {
    "hospital": KIND_HOSPITAL,
    "clinic": KIND_CLINIC,
    "centre": KIND_CLINIC,
    "center": KIND_CLINIC,
    "doctor": KIND_DOCTOR,
    "physician": KIND_DOCTOR,
    "pharmacy": KIND_PHARMACY,
    "laboratory": KIND_LABORATORY,
    "sample_collection": KIND_LABORATORY,
}

# How well a facility category serves a search for another category. A search
# for a doctor is largely satisfied by a clinic; it is not satisfied at all by a
# pharmacy. Values are deliberately explicit rather than derived, so a ranking
# change is a visible edit here.
_KIND_AFFINITY: Dict[str, Dict[str, float]] = {
    KIND_DOCTOR: {
        KIND_DOCTOR: 1.0,
        KIND_CLINIC: 0.75,
        KIND_HOSPITAL: 0.55,
        KIND_LABORATORY: 0.0,
        KIND_PHARMACY: 0.0,
    },
    KIND_HOSPITAL: {
        KIND_HOSPITAL: 1.0,
        KIND_CLINIC: 0.60,
        KIND_DOCTOR: 0.40,
        KIND_LABORATORY: 0.20,
        KIND_PHARMACY: 0.0,
    },
    KIND_CLINIC: {
        KIND_CLINIC: 1.0,
        KIND_DOCTOR: 0.80,
        KIND_HOSPITAL: 0.60,
        KIND_LABORATORY: 0.20,
        KIND_PHARMACY: 0.0,
    },
    KIND_PHARMACY: {
        KIND_PHARMACY: 1.0,
        KIND_HOSPITAL: 0.20,
        KIND_CLINIC: 0.10,
        KIND_DOCTOR: 0.0,
        KIND_LABORATORY: 0.0,
    },
    KIND_LABORATORY: {
        KIND_LABORATORY: 1.0,
        KIND_HOSPITAL: 0.40,
        KIND_CLINIC: 0.30,
        KIND_DOCTOR: 0.0,
        KIND_PHARMACY: 0.0,
    },
}

# A requested specialty the provider does not publish does not disqualify it -
# the facility category may still be right - but it must not score as though the
# specialty were confirmed. Nothing here infers a specialty the source omitted.
_UNCONFIRMED_SPECIALTY_FACTOR = 0.60

# Clinical topic to specialty. Used only to choose what to search for; it never
# labels a provider. Ordered most specific first, and the first hit wins.
_FINDING_SPECIALTY_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("cardiology", ("cardio", "heart", "blood pressure", "hypertension", "cholesterol", "lipid", "ecg", "arrhythm")),
    ("endocrinology", ("diabet", "thyroid", "endocrin", "insulin", "hba1c", "glucose")),
    ("nephrology", ("kidney", "renal", "nephro", "creatinine", "egfr", "dialysis")),
    ("pulmonology", ("lung", "respirat", "asthma", "copd", "pulmon", "breath")),
    ("gastroenterology", ("liver", "hepat", "gastro", "stomach", "intestin", "bowel", "alt", "ast")),
    ("neurology", ("neuro", "seizure", "epilep", "migraine", "stroke", "nerve")),
    ("dermatology", ("derma", "skin", "rash", "eczema", "psoria")),
    ("haematology", ("haemo", "hemo", "anaemia", "anemia", "platelet", "clotting", "haematol")),
    ("oncology", ("oncolog", "tumour", "tumor", "cancer", "malignan")),
    ("rheumatology", ("rheumat", "arthrit", "joint", "lupus")),
    ("ophthalmology", ("ophthalm", "vision", "retina", "glaucoma")),
    ("psychiatry", ("psychiat", "depress", "anxiety", "mental health")),
)


@dataclass(frozen=True)
class ProviderCandidate:
    """
    One healthcare facility as published by the source, before ranking.

    Every optional field is None when the source did not publish it. None means
    "not published"; it never means zero, and it is never replaced by a guess.
    """

    name: str
    kind: str
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    opening_hours: Optional[str]
    specialties: Tuple[str, ...]
    source: str
    source_element_id: Optional[str]


@dataclass(frozen=True)
class MatchBreakdown:
    """
    The four components of a match score. They always sum to the score.
    """

    specialty: float
    distance: float
    completeness: float
    verified: float

    @property
    def total(self) -> float:
        return round(self.specialty + self.distance + self.completeness + self.verified, 2)


@dataclass(frozen=True)
class RankedProvider:
    """A candidate together with its computed distance and score."""

    candidate: ProviderCandidate
    distance_km: Optional[float]
    match_score: float
    match_breakdown: MatchBreakdown


def _clean_text(value: Any) -> Optional[str]:
    """Returns trimmed text, or None when the source published nothing usable."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class ProviderDiscoveryService:
    """
    Pure discovery and ranking logic for healthcare providers.

    No method touches the network, the database or the clock. Given the same
    inputs, every method returns the same output.
    """

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def haversine_km(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Great-circle distance between two points in kilometres.

        This is a straight-line distance over the surface of the Earth. It is
        not travel distance and is never presented as one.
        """
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))

    def distance_from(
        self,
        origin_lat: Optional[float],
        origin_lon: Optional[float],
        candidate: ProviderCandidate,
    ) -> Optional[float]:
        """
        Distance from the resolved search origin to a candidate, or None when
        either side lacks coordinates. An unknown distance stays unknown.
        """
        if origin_lat is None or origin_lon is None:
            return None
        if candidate.latitude is None or candidate.longitude is None:
            return None
        return round(
            self.haversine_km(origin_lat, origin_lon, candidate.latitude, candidate.longitude),
            3,
        )

    # ------------------------------------------------------------------
    # Search scope encoding (DoctorRecommendation.specialty)
    # ------------------------------------------------------------------

    def normalize_specialty(self, value: Optional[str]) -> Optional[str]:
        """
        Reduces a specialty to the lowercase hyphenated form used in the scope.

        Returns None for anything that normalizes to nothing, so a meaningless
        specialty is dropped rather than encoded.
        """
        text = _clean_text(value)
        if text is None:
            return None

        normalized = _SPECIALTY_STRIP_PATTERN.sub("-", text.lower())
        normalized = _SPECIALTY_COLLAPSE_PATTERN.sub("-", normalized).strip("-")
        if not normalized:
            return None
        return normalized[:_SPECIALTY_MAX_LENGTH].strip("-") or None

    def build_search_scope(self, kind: str, specialty: Optional[str] = None) -> str:
        """
        Encodes a facility category and optional specialty into the string
        stored in DoctorRecommendation.specialty.

        A hospital search encodes as "hospital"; a doctor search carrying a
        specialty encodes as "doctor:cardiology". A specialty is included only
        when one was actually established - it is never invented to fill the
        suffix.
        """
        clean_kind = (_clean_text(kind) or "").lower()
        if clean_kind not in PROVIDER_KINDS:
            raise ValueError(
                f"Unknown provider kind '{kind}'. Expected one of: {', '.join(PROVIDER_KINDS)}."
            )

        normalized = self.normalize_specialty(specialty)
        if not normalized:
            return clean_kind
        return f"{clean_kind}{_SCOPE_SEPARATOR}{normalized}"

    def parse_search_scope(self, scope: Optional[str]) -> Tuple[Optional[str], Tuple[str, ...]]:
        """
        Decodes a stored scope back into a facility category and its specialties.

        "hospital" yields ("hospital", ()); "doctor:cardiology" yields
        ("doctor", ("cardiology",)). An unrecognised scope yields (None, ()) so
        a reader can report the record as unclassified rather than mislabel it.
        """
        text = _clean_text(scope)
        if text is None:
            return None, ()

        kind, separator, specialty = text.lower().partition(_SCOPE_SEPARATOR)
        kind = kind.strip()
        if kind not in PROVIDER_KINDS:
            logger.debug("Unrecognised provider search scope: %r", scope)
            return None, ()

        if not separator:
            return kind, ()

        normalized = self.normalize_specialty(specialty)
        return kind, ((normalized,) if normalized else ())

    # ------------------------------------------------------------------
    # Specialty derivation
    # ------------------------------------------------------------------

    def derive_specialty(
        self,
        finding_type: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[str]:
        """
        Chooses the specialty to search for from a clinical finding's text.

        Returns None when no topic is recognised, which the caller turns into a
        general hospital search. It never returns a specialty on a guess: only
        an explicit keyword match produces one.
        """
        haystack = " ".join(
            part.lower() for part in (finding_type, title, description) if part
        )
        if not haystack.strip():
            return None

        for specialty, keywords in _FINDING_SPECIALTY_KEYWORDS:
            if any(keyword in haystack for keyword in keywords):
                return specialty
        return None

    # ------------------------------------------------------------------
    # Overpass payload parsing
    # ------------------------------------------------------------------

    def parse_overpass_element(self, element: Any) -> Optional[ProviderCandidate]:
        """
        Converts one Overpass element into a candidate.

        Returns None when the element is not a recognisable healthcare facility
        or has no published name. A nameless facility is dropped rather than
        shown as "Unnamed clinic", because that label would be our invention.
        """
        if not isinstance(element, dict):
            return None

        tags = element.get("tags")
        if not isinstance(tags, dict):
            return None

        kind = self._element_kind(tags)
        if kind is None:
            return None

        name = (
            _clean_text(tags.get("name"))
            or _clean_text(tags.get("official_name"))
            or _clean_text(tags.get("operator"))
        )
        if name is None:
            return None

        latitude, longitude = self._element_coordinates(element)

        element_id = element.get("id")
        element_type = _clean_text(element.get("type"))
        source_element_id = (
            f"{element_type}/{element_id}" if element_type and element_id is not None
            else (str(element_id) if element_id is not None else None)
        )

        return ProviderCandidate(
            name=name,
            kind=kind,
            latitude=latitude,
            longitude=longitude,
            address=self._element_address(tags),
            phone=_clean_text(tags.get("phone")) or _clean_text(tags.get("contact:phone")),
            website=_clean_text(tags.get("website")) or _clean_text(tags.get("contact:website")),
            opening_hours=_clean_text(tags.get("opening_hours")),
            specialties=self._element_specialties(tags),
            source=SOURCE_OPENSTREETMAP,
            source_element_id=source_element_id,
        )

    def parse_overpass_response(self, payload: Any) -> List[ProviderCandidate]:
        """
        Converts an Overpass JSON response into candidates, skipping anything
        that cannot be read. A malformed payload yields an empty list rather
        than an exception, so a bad upstream response degrades to "no results
        found" instead of a crash.
        """
        if not isinstance(payload, dict):
            return []

        elements = payload.get("elements")
        if not isinstance(elements, list):
            return []

        candidates: List[ProviderCandidate] = []
        seen: set = set()
        for element in elements:
            candidate = self.parse_overpass_element(element)
            if candidate is None:
                continue
            # Overpass can return the same facility as both a node and a way.
            key = candidate.source_element_id or (
                candidate.name,
                candidate.latitude,
                candidate.longitude,
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)

        return candidates

    def _element_kind(self, tags: Dict[str, Any]) -> Optional[str]:
        """Reads the facility category from the amenity or healthcare tag."""
        amenity = (_clean_text(tags.get("amenity")) or "").lower()
        if amenity in _AMENITY_KIND:
            return _AMENITY_KIND[amenity]

        healthcare = (_clean_text(tags.get("healthcare")) or "").lower()
        if healthcare in _HEALTHCARE_KIND:
            return _HEALTHCARE_KIND[healthcare]

        return None

    def _element_coordinates(self, element: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """
        Reads coordinates from a node, or from the computed centre of a way or
        relation. Non-numeric values are treated as absent.
        """
        latitude, longitude = element.get("lat"), element.get("lon")
        if latitude is None or longitude is None:
            center = element.get("center")
            if isinstance(center, dict):
                latitude, longitude = center.get("lat"), center.get("lon")

        try:
            if latitude is None or longitude is None:
                return None, None
            return float(latitude), float(longitude)
        except (TypeError, ValueError):
            return None, None

    def _element_address(self, tags: Dict[str, Any]) -> Optional[str]:
        """
        Assembles a street address from the published addr:* tags.

        Only published parts are joined; nothing is filled in, so a partial
        address stays partial rather than becoming a plausible-looking whole.
        """
        full = _clean_text(tags.get("addr:full"))
        if full:
            return full

        house_number = _clean_text(tags.get("addr:housenumber"))
        street = _clean_text(tags.get("addr:street"))
        line = " ".join(part for part in (house_number, street) if part) or None

        parts = [
            line,
            _clean_text(tags.get("addr:suburb")),
            _clean_text(tags.get("addr:city")),
            _clean_text(tags.get("addr:postcode")),
        ]
        joined = ", ".join(part for part in parts if part)
        return joined or None

    def _element_specialties(self, tags: Dict[str, Any]) -> Tuple[str, ...]:
        """
        Reads published specialities, which Overpass returns semicolon-separated.
        Absent when the source published none - never inferred from the category.
        """
        raw = _clean_text(tags.get("healthcare:speciality")) or _clean_text(tags.get("healthcare:specialty"))
        if raw is None:
            return ()

        specialties: List[str] = []
        for part in raw.split(";"):
            normalized = self.normalize_specialty(part)
            if normalized and normalized not in specialties:
                specialties.append(normalized)
        return tuple(specialties)

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def score(
        self,
        candidate: ProviderCandidate,
        requested_kind: str,
        requested_specialty: Optional[str] = None,
        distance_km: Optional[float] = None,
        radius_km: Optional[float] = None,
        availability_preference: Optional[str] = None,
    ) -> MatchBreakdown:
        """
        Scores one candidate from 0 to 100.

        Every input is a value that is persisted - the search's scope, radius
        and availability preference, and the recommendation's distance and
        contact fields - so re-scoring a stored row reproduces this result
        exactly.

        Availability shifts weight inside the completeness component towards
        published opening hours: knowing a facility's hours matters more to
        someone who stated when they are free. It never asserts that the
        facility is open then, and no appointment time is derived from it.
        """
        specialty_points = self._specialty_points(candidate, requested_kind, requested_specialty)
        distance_points = self._distance_points(distance_km, radius_km)
        completeness_points = self._completeness_points(candidate, availability_preference)
        verified_points = self._verified_points(candidate)

        return MatchBreakdown(
            specialty=round(specialty_points, 2),
            distance=round(distance_points, 2),
            completeness=round(completeness_points, 2),
            verified=round(verified_points, 2),
        )

    def _specialty_points(
        self,
        candidate: ProviderCandidate,
        requested_kind: str,
        requested_specialty: Optional[str],
    ) -> float:
        """Facility-category fit, reduced when a requested specialty is unconfirmed."""
        affinities = _KIND_AFFINITY.get((requested_kind or "").lower())
        if not affinities:
            return 0.0

        affinity = affinities.get(candidate.kind, 0.0)
        if affinity <= 0.0:
            return 0.0

        normalized = self.normalize_specialty(requested_specialty)
        if normalized is None or normalized in candidate.specialties:
            return SPECIALTY_WEIGHT * affinity
        return SPECIALTY_WEIGHT * affinity * _UNCONFIRMED_SPECIALTY_FACTOR

    def _distance_points(self, distance_km: Optional[float], radius_km: Optional[float]) -> float:
        """
        Linear decay from full marks at the origin to zero at the radius.

        An unknown distance scores zero rather than an average: a facility whose
        location the source omitted has not earned proximity points.
        """
        if distance_km is None or radius_km is None or radius_km <= 0:
            return 0.0
        if distance_km <= 0:
            return DISTANCE_WEIGHT
        if distance_km >= radius_km:
            return 0.0
        return DISTANCE_WEIGHT * (1.0 - (distance_km / radius_km))

    def _completeness_points(
        self,
        candidate: ProviderCandidate,
        availability_preference: Optional[str],
    ) -> float:
        """
        How reachable the provider is from what the source published.

        With no availability preference the three contact channels weigh
        equally. With one, published opening hours weigh more heavily; the total
        available from this component is unchanged either way.
        """
        if _clean_text(availability_preference):
            hours_weight, phone_weight, website_weight = 7.0, 4.0, 4.0
        else:
            hours_weight, phone_weight, website_weight = 5.0, 5.0, 5.0

        points = 0.0
        if candidate.opening_hours:
            points += hours_weight
        if candidate.phone:
            points += phone_weight
        if candidate.website:
            points += website_weight
        return points

    def _verified_points(self, candidate: ProviderCandidate) -> float:
        """Record-quality signals: a location, an address and a stated specialty."""
        points = 0.0
        if candidate.latitude is not None and candidate.longitude is not None:
            points += 5.0
        if candidate.address:
            points += 5.0
        if candidate.specialties:
            points += 5.0
        return points

    def rank(
        self,
        candidates: Sequence[ProviderCandidate],
        requested_kind: str,
        requested_specialty: Optional[str] = None,
        origin_lat: Optional[float] = None,
        origin_lon: Optional[float] = None,
        radius_km: Optional[float] = None,
        availability_preference: Optional[str] = None,
    ) -> List[RankedProvider]:
        """
        Scores every candidate and returns them best first.

        Ties break on distance then name, so an identical result set always
        comes back in an identical order. Candidates are never dropped here:
        filtering by radius belongs to the query that fetched them, and a
        zero-scoring provider is still a real facility the source returned.
        """
        ranked: List[RankedProvider] = []
        for candidate in candidates:
            distance_km = self.distance_from(origin_lat, origin_lon, candidate)
            breakdown = self.score(
                candidate=candidate,
                requested_kind=requested_kind,
                requested_specialty=requested_specialty,
                distance_km=distance_km,
                radius_km=radius_km,
                availability_preference=availability_preference,
            )
            ranked.append(
                RankedProvider(
                    candidate=candidate,
                    distance_km=distance_km,
                    match_score=breakdown.total,
                    match_breakdown=breakdown,
                )
            )

        ranked.sort(
            key=lambda item: (
                -item.match_score,
                item.distance_km if item.distance_km is not None else math.inf,
                item.candidate.name.lower(),
            )
        )
        return ranked


_default_provider_discovery_service: Optional[ProviderDiscoveryService] = None


def get_provider_discovery_service() -> ProviderDiscoveryService:
    """Return the shared ProviderDiscoveryService instance."""

    global _default_provider_discovery_service

    if _default_provider_discovery_service is None:
        _default_provider_discovery_service = ProviderDiscoveryService()

    return _default_provider_discovery_service
