"""
Deterministic, read-only analysis service for patient laboratory results.

The service:
- Reuses the existing LabResult model.
- Never writes to the database.
- Receives an already-resolved patient_id from the API layer.
- Classifies numeric laboratory values against their reference ranges.
- Handles malformed values safely as UNKNOWN.
- Builds historical trend information from persisted lab results.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.lab_result import LabResult

logger = logging.getLogger(__name__)

STATUS_NORMAL = "NORMAL"
STATUS_HIGH = "HIGH"
STATUS_LOW = "LOW"
STATUS_UNKNOWN = "UNKNOWN"

TREND_INCREASING = "INCREASING"
TREND_DECREASING = "DECREASING"
TREND_STABLE = "STABLE"
TREND_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# Markers that make a reported value something other than one exact
# measurement: censored ("<0.01", ">1000"), approximate ("~5") or a
# measurement with a tolerance ("5 +/- 1"). Treating "<0.01" as 0.01 would
# invent a precision the laboratory explicitly declined to report, so any
# value carrying one of these is classified UNKNOWN instead.
_CENSORED_VALUE_MARKERS = ("<", ">", "≤", "≥", "~", "±")

# A comma cannot be resolved without knowing the source locale: "1,200" is
# 1200 under en-US grouping and 1.2 under de-DE decimal notation. Both
# readings are plausible for a laboratory value, so neither is guessed.
_AMBIGUOUS_SEPARATOR = ","

# A value is accepted only when the whole string is one number optionally
# followed by a unit. Anchoring both ends is what rejects "1,200" (trailing
# ",200"), "3.5 - 5.5" (a range in the value column) and "Grade 2 at 5.2".
# The unit, when present, must start with a non-numeric character so that a
# second number can never be silently discarded.
_NUMERIC_VALUE_PATTERN = re.compile(
    r"^(?P<number>[-+]?(?:\d+(?:\.\d+)?|\.\d+))"
    r"(?:\s*[A-Za-z%/^(\[].*)?$"
)

# Scientific notation would otherwise be truncated by the pattern above:
# "1e3" matches with number "1" and unit "e3", reporting 1 instead of 1000.
# It is rejected rather than parsed, keeping this parser to plain decimals.
_SCIENTIFIC_NOTATION_PATTERN = re.compile(
    r"^[-+]?(?:\d+(?:\.\d+)?|\.\d+)[eE][-+]?\d+$"
)


@dataclass(frozen=True)
class LabResultAnalysis:
    """Analysis result for one laboratory record."""

    id: UUID
    test_name: str
    value: str
    numeric_value: Optional[float]
    unit: Optional[str]
    reference_range: Optional[str]
    result_date: Optional[date]
    status: str
    source_document_id: Optional[UUID]
    source_document_name: Optional[str]


@dataclass(frozen=True)
class LabTrendPoint:
    """One historical point for a laboratory test."""

    result_date: Optional[date]
    value: str
    numeric_value: Optional[float]
    unit: Optional[str]
    status: str
    source_document_id: Optional[UUID]
    source_document_name: Optional[str]


@dataclass(frozen=True)
class LabTrend:
    """Historical trend for one laboratory test."""

    test_name: str
    unit: Optional[str]
    trend: str
    points: Tuple[LabTrendPoint, ...]


class LabIntelligenceService:
    """
    Stateless and read-only laboratory intelligence service.

    The API layer is responsible for authentication and resolving the
    authenticated user to a Patient. This service receives patient_id and
    applies it to every database query.
    """

    def analyze_patient_labs(
        self,
        db: Session,
        patient_id: UUID,
    ) -> Tuple[LabResultAnalysis, ...]:
        """
        Analyze all laboratory results belonging to one patient.

        Dated results come first, newest first; undated results come last.
        This matches the ordering of GET /records/lab-results. NULL handling is
        stated explicitly rather than left to the backend default, which differs
        between PostgreSQL (NULLs first under DESC) and SQLite (NULLs last).

        The trailing id tiebreak is what makes the order total: created_at
        defaults to now(), which PostgreSQL evaluates once per transaction, so
        results imported together share an identical timestamp.
        """

        lab_results = (
            db.query(LabResult)
            .options(joinedload(LabResult.document))
            .filter(LabResult.patient_id == patient_id)
            .order_by(
                LabResult.result_date.desc().nullslast(),
                LabResult.created_at.desc(),
                LabResult.id.asc(),
            )
            .all()
        )

        analyses = tuple(
            self._analyze_result(lab_result)
            for lab_result in lab_results
        )

        logger.info(
            "Lab intelligence analysis for patient %s: %d results",
            patient_id,
            len(analyses),
        )

        return analyses

    def get_test_trend(
        self,
        db: Session,
        patient_id: UUID,
        test_name: str,
    ) -> LabTrend:
        """
        Build the historical trend for one laboratory test.

        Matching is case-insensitive, ignores surrounding whitespace, and is
        scoped to the supplied patient, so a test name held by another patient
        never matches here.

        Points run oldest to newest; undated results sort last, preserving the
        PostgreSQL ordering the API already serves. An empty points tuple means
        the patient has no result under this name, which is how the API layer
        distinguishes a missing test from one with too little data to trend.
        """

        normalized_test_name = test_name.strip().lower()

        if not normalized_test_name:
            return LabTrend(
                test_name=test_name,
                unit=None,
                trend=TREND_INSUFFICIENT_DATA,
                points=(),
            )

        matching_results = [
            result
            for result in self._fetch_chronological_results(db, patient_id)
            if result.test_name.strip().lower() == normalized_test_name
        ]

        display_name = (
            matching_results[0].test_name
            if matching_results
            else test_name
        )

        return self._build_trend(display_name, matching_results)

    def get_all_test_trends(
        self,
        db: Session,
        patient_id: UUID,
    ) -> Tuple[LabTrend, ...]:
        """
        Build the historical trend for every test the patient has results for.

        Fetches once and groups in Python rather than calling get_test_trend per
        test name, which would issue one query per test. Both paths share
        _build_trend, so trend direction is still calculated in exactly one
        place. Trends follow the alphabetical ordering of get_available_tests.
        """

        grouped: Dict[str, List[LabResult]] = {}
        display_names: Dict[str, str] = {}

        for result in self._fetch_chronological_results(db, patient_id):
            key = result.test_name.strip().lower()

            if not key:
                continue

            grouped.setdefault(key, []).append(result)
            display_names.setdefault(key, result.test_name.strip())

        return tuple(
            self._build_trend(display_names[key], grouped[key])
            for key in sorted(grouped)
        )

    def _fetch_chronological_results(
        self,
        db: Session,
        patient_id: UUID,
    ) -> List[LabResult]:
        """
        Fetch the patient's laboratory results oldest first.

        The source document is eager-loaded because every result is mapped to a
        response carrying its document name; lazy loading would issue one query
        per result.
        """

        return (
            db.query(LabResult)
            .options(joinedload(LabResult.document))
            .filter(
                LabResult.patient_id == patient_id,
                LabResult.test_name.isnot(None),
            )
            .order_by(
                LabResult.result_date.asc().nullslast(),
                LabResult.created_at.asc(),
                LabResult.id.asc(),
            )
            .all()
        )

    def _build_trend(
        self,
        display_name: str,
        results: List[LabResult],
    ) -> LabTrend:
        """
        Assemble one LabTrend from already-fetched, chronologically ordered rows.

        The single place trend direction is calculated, shared by get_test_trend
        and get_all_test_trends.
        """

        points = tuple(self._trend_point(result) for result in results)

        return LabTrend(
            test_name=display_name,
            unit=results[-1].unit if results else None,
            trend=self._calculate_trend(points),
            points=points,
        )

    def get_available_tests(
        self,
        db: Session,
        patient_id: UUID,
    ) -> Tuple[str, ...]:
        """Return distinct laboratory test names for the patient."""

        lab_results = (
            db.query(LabResult.test_name)
            .filter(
                LabResult.patient_id == patient_id,
                LabResult.test_name.isnot(None),
            )
            .order_by(LabResult.test_name.asc(), LabResult.id.asc())
            .all()
        )

        names: Dict[str, str] = {}

        for row in lab_results:
            name = row[0]

            if not name:
                continue

            normalized = name.strip().lower()

            if normalized:
                names.setdefault(normalized, name.strip())

        return tuple(sorted(names.values(), key=str.lower))

    def _analyze_result(
        self,
        lab_result: LabResult,
    ) -> LabResultAnalysis:
        """Convert a LabResult database row into an analyzed result."""

        numeric_value = self._parse_numeric_value(lab_result.value)

        status = self._determine_status(
            numeric_value=numeric_value,
            reference_range=lab_result.reference_range,
        )

        return LabResultAnalysis(
            id=lab_result.id,
            test_name=lab_result.test_name,
            value=lab_result.value,
            numeric_value=numeric_value,
            unit=lab_result.unit,
            reference_range=lab_result.reference_range,
            result_date=lab_result.result_date,
            status=status,
            source_document_id=lab_result.document_id,
            source_document_name=self._source_document_name(lab_result),
        )

    @staticmethod
    def _source_document_name(lab_result: LabResult) -> Optional[str]:
        """
        Read the display name of the document a result was extracted from.

        Only file_name is surfaced. file_path is internal storage location and
        must never reach a response schema.
        """

        document = lab_result.document

        return document.file_name if document else None

    @staticmethod
    def _trend_point(
        lab_result: LabResult,
    ) -> LabTrendPoint:
        """Convert one LabResult into a trend point."""

        numeric_value = LabIntelligenceService._parse_numeric_value(
            lab_result.value
        )

        status = LabIntelligenceService._determine_status(
            numeric_value=numeric_value,
            reference_range=lab_result.reference_range,
        )

        return LabTrendPoint(
            result_date=lab_result.result_date,
            value=lab_result.value,
            numeric_value=numeric_value,
            unit=lab_result.unit,
            status=status,
            source_document_id=lab_result.document_id,
            source_document_name=LabIntelligenceService._source_document_name(
                lab_result
            ),
        )

    @staticmethod
    def _parse_numeric_value(
        value: Optional[str],
    ) -> Optional[float]:
        """
        Parse the numeric component of a laboratory value.

        Only a value that is unambiguously one exact number is parsed. Anything
        censored, approximate, locale-dependent or otherwise open to more than
        one reading returns None, which the caller reports as UNKNOWN. Reporting
        UNKNOWN is safe; inventing a precise number the laboratory did not state
        would produce a confident NORMAL/HIGH/LOW verdict on the wrong figure.

        Accepted:
            "5.2" -> 5.2
            "5.2 mg/dL" -> 5.2
            "  5.2  " -> 5.2
            "-1.5" -> -1.5

        Rejected (None):
            "<0.01" -> censored lower limit, not the value 0.01
            ">1000" -> censored upper limit, not the value 1000
            "1,200" -> 1200 or 1.2 depending on locale
            "3.5 - 5.5" -> a range, not a single measurement
            "1e3" -> scientific notation is not parsed
            "not available" -> no number at all
        """

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        if any(marker in text for marker in _CENSORED_VALUE_MARKERS):
            return None

        if _AMBIGUOUS_SEPARATOR in text:
            return None

        if _SCIENTIFIC_NOTATION_PATTERN.match(text):
            return None

        match = _NUMERIC_VALUE_PATTERN.match(text)

        if not match:
            return None

        try:
            return float(match.group("number"))
        except ValueError:
            return None

    @staticmethod
    def _parse_reference_range(
        reference_range: Optional[str],
    ) -> Optional[Tuple[float, float]]:
        """
        Parse a numeric reference range.

        Supported examples:

            "3.5 - 5.5"
            "3.5–5.5"
            "3.5 to 5.5"
            "3.5 - 5.5 mg/dL"

        Returns None for malformed or unsupported ranges.
        """

        if reference_range is None:
            return None

        text = str(reference_range).strip()

        if not text:
            return None

        # A grouping/decimal comma is as ambiguous in a bound as it is in a
        # value ("1,200 - 1,500"), and a misread bound silently reclassifies
        # every result measured against it.
        if _AMBIGUOUS_SEPARATOR in text:
            return None

        normalized = text.lower().replace("–", "-").replace("—", "-")

        match = re.search(
            r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))"
            r"\s*(?:-|to)\s*"
            r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))",
            normalized,
        )

        if not match:
            return None

        try:
            lower = float(match.group(1))
            upper = float(match.group(2))
        except ValueError:
            return None

        if lower > upper:
            return None

        return lower, upper

    @classmethod
    def _determine_status(
        cls,
        numeric_value: Optional[float],
        reference_range: Optional[str],
    ) -> str:
        """
        Determine NORMAL, HIGH, LOW or UNKNOWN.

        Boundary values are considered NORMAL.
        """

        if numeric_value is None:
            return STATUS_UNKNOWN

        parsed_range = cls._parse_reference_range(reference_range)

        if parsed_range is None:
            return STATUS_UNKNOWN

        lower, upper = parsed_range

        if numeric_value < lower:
            return STATUS_LOW

        if numeric_value > upper:
            return STATUS_HIGH

        return STATUS_NORMAL

    @staticmethod
    def _calculate_trend(
        points: Tuple[LabTrendPoint, ...],
    ) -> str:
        """
        Calculate a neutral historical direction.

        Fewer than two numeric points means there is not enough information
        to establish a direction.

        A small relative change is treated as stable.
        """

        numeric_points = [
            point
            for point in points
            if point.numeric_value is not None
        ]

        if len(numeric_points) < 2:
            return TREND_INSUFFICIENT_DATA

        first = numeric_points[0].numeric_value
        last = numeric_points[-1].numeric_value

        if first is None or last is None:
            return TREND_INSUFFICIENT_DATA

        if first == 0:
            difference = last - first

            if difference == 0:
                return TREND_STABLE

            return (
                TREND_INCREASING
                if difference > 0
                else TREND_DECREASING
            )

        relative_change = abs(last - first) / abs(first)

        if relative_change <= 0.05:
            return TREND_STABLE

        if last > first:
            return TREND_INCREASING

        return TREND_DECREASING


_default_lab_intelligence_service: Optional[LabIntelligenceService] = None


def get_lab_intelligence_service() -> LabIntelligenceService:
    """Return the shared LabIntelligenceService instance."""

    global _default_lab_intelligence_service

    if _default_lab_intelligence_service is None:
        _default_lab_intelligence_service = LabIntelligenceService()

    return _default_lab_intelligence_service