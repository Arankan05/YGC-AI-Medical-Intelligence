"""
Deterministic single-dose ceiling rules for the Medication Safety &
Clinical Contraindication Engine.

IMPORTANT - SCOPE AND LIMITATIONS OF THIS DATASET:

This module is NOT a clinical dosage database. It is a small, hand-written demo
dataset for a competition project, and it must not be relied upon for real
prescribing decisions. Specifically, the ceilings below:

- Apply to a single administered dose only. Cumulative daily totals are NOT
  evaluated, because Prescription.frequency is free text ("twice daily", "TID",
  "PRN") that cannot be parsed deterministically.
- Assume a typical adult patient. Paediatric, elderly, pregnancy, renal and
  hepatic dose adjustments are not modelled.
- Ignore the indication. Several medicines are legitimately prescribed above
  these ceilings for specific conditions or under specialist supervision.
- Cover only the handful of medicines listed. Any medicine absent from the
  dataset is never evaluated and never flagged.

Design Principles:
- Deterministic: A dose is compared against a configured number. No AI provider
  or external API is consulted, and no ceiling is inferred at runtime.
- Conservative: A dosage string that cannot be parsed with confidence, or whose
  unit cannot be compared with the configured ceiling, is reported as "not
  evaluated" rather than guessed to be unsafe.
- Consistent normalization: Medication names are matched with the same
  normalization used everywhere else in the engine.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.services.medication_interactions import (
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    normalize_medication_name,
)


@dataclass(frozen=True)
class DosageAmount:
    """
    A dose parsed from free text and converted to a canonical unit.

    Attributes:
        value: Numeric amount expressed in the canonical unit.
        unit: Canonical unit ("mg", "ml", "iu" or "tablet").
        original: The raw dosage string this was parsed from.
    """
    value: float
    unit: str
    original: str


@dataclass(frozen=True)
class DosageLimit:
    """
    The configured maximum single dose for one medication.

    Attributes:
        medication: Normalized medication name.
        max_single_dose: Highest single dose considered routine.
        unit: Canonical unit the ceiling is expressed in.
        severity: Risk level to report when the ceiling is exceeded.
        note: Short clinical context shown to the patient.
    """
    medication: str
    max_single_dose: float
    unit: str
    severity: str
    note: str


@dataclass(frozen=True)
class DosageExceedance:
    """
    Result of a dose that exceeds its configured ceiling.

    Attributes:
        medication: Normalized medication name.
        dose: The parsed dose that was evaluated.
        limit: The ceiling the dose exceeded.
        severity: Risk level for this exceedance.
        description: Plain-language explanation of the concern.
    """
    medication: str
    dose: DosageAmount
    limit: DosageLimit
    severity: str
    description: str


# Maximum single doses for a small set of common medicines.
#
# Each entry is (medication, max_single_dose, unit, severity, note). Values are
# routine adult single-dose ceilings; see the module docstring for everything
# this deliberately does not model. Keep this list small and easy to review.
_DOSAGE_LIMIT_DEFINITIONS: Tuple[Tuple[str, float, str, str, str], ...] = (
    (
        "paracetamol",
        1000.0,
        "mg",
        SEVERITY_HIGH,
        "Doses above 1000 mg at once raise the risk of liver injury.",
    ),
    (
        "ibuprofen",
        800.0,
        "mg",
        SEVERITY_MEDIUM,
        "Single doses above 800 mg increase the risk of stomach and kidney side effects.",
    ),
    (
        "aspirin",
        1000.0,
        "mg",
        SEVERITY_MEDIUM,
        "Single doses above 1000 mg increase the risk of stomach irritation and bleeding.",
    ),
    (
        "naproxen",
        500.0,
        "mg",
        SEVERITY_MEDIUM,
        "Single doses above 500 mg increase the risk of stomach and kidney side effects.",
    ),
    (
        "amoxicillin",
        1000.0,
        "mg",
        SEVERITY_MEDIUM,
        "Routine adult single doses do not usually exceed 1000 mg.",
    ),
    (
        "metformin",
        1000.0,
        "mg",
        SEVERITY_MEDIUM,
        "Single doses above 1000 mg increase the risk of digestive side effects.",
    ),
    (
        "lisinopril",
        40.0,
        "mg",
        SEVERITY_MEDIUM,
        "Routine adult daily dosing does not usually exceed 40 mg.",
    ),
    (
        "amlodipine",
        10.0,
        "mg",
        SEVERITY_MEDIUM,
        "Routine adult daily dosing does not usually exceed 10 mg.",
    ),
    (
        "simvastatin",
        80.0,
        "mg",
        SEVERITY_MEDIUM,
        "Doses above 80 mg are not routinely used and increase the risk of muscle damage.",
    ),
    (
        "sertraline",
        200.0,
        "mg",
        SEVERITY_MEDIUM,
        "Routine adult daily dosing does not usually exceed 200 mg.",
    ),
    (
        "warfarin",
        10.0,
        "mg",
        SEVERITY_HIGH,
        "Single doses above 10 mg are unusual outside supervised loading and raise bleeding risk.",
    ),
)

# Recognised dose units, mapped to (canonical unit, multiplier). Units in the
# same canonical family are comparable; units in different families are not.
_UNIT_ALIASES: Dict[str, Tuple[str, float]] = {
    # Mass, canonicalised to milligrams.
    "mcg": ("mg", 0.001),
    "ug": ("mg", 0.001),
    "µg": ("mg", 0.001),
    "μg": ("mg", 0.001),
    "microgram": ("mg", 0.001),
    "micrograms": ("mg", 0.001),
    "mg": ("mg", 1.0),
    "mgs": ("mg", 1.0),
    "milligram": ("mg", 1.0),
    "milligrams": ("mg", 1.0),
    "g": ("mg", 1000.0),
    "gm": ("mg", 1000.0),
    "gram": ("mg", 1000.0),
    "grams": ("mg", 1000.0),
    # Volume, canonicalised to millilitres.
    "ml": ("ml", 1.0),
    "mls": ("ml", 1.0),
    "milliliter": ("ml", 1.0),
    "milliliters": ("ml", 1.0),
    "millilitre": ("ml", 1.0),
    "millilitres": ("ml", 1.0),
    "l": ("ml", 1000.0),
    "litre": ("ml", 1000.0),
    "liter": ("ml", 1000.0),
    # International units.
    "iu": ("iu", 1.0),
    "ius": ("iu", 1.0),
    # Countable forms. Parsed so they are recognised as valid dosage text, but
    # they are never comparable with a mass or volume ceiling.
    "tab": ("tablet", 1.0),
    "tabs": ("tablet", 1.0),
    "tablet": ("tablet", 1.0),
    "tablets": ("tablet", 1.0),
    "cap": ("tablet", 1.0),
    "caps": ("tablet", 1.0),
    "capsule": ("tablet", 1.0),
    "capsules": ("tablet", 1.0),
}

# A dosage string is only accepted when it is exactly one number followed by one
# recognised unit, e.g. "500mg", "1000 mg", "5 mg", "1 g". Anything else (ranges
# such as "500-1000mg", compound instructions, or digit grouping such as
# "1,000 mg" whose meaning is locale-dependent) is treated as unparseable.
_DOSAGE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([a-zµμ]+)$")


def parse_dosage(dosage_text: Optional[str]) -> Optional[DosageAmount]:
    """
    Parses a free-text dosage string into a canonical amount.

    Accepts a single number followed by a recognised unit, with or without a
    space ("500mg", "1000 mg", "5 mg", "1 g", "10 ml", "1 tablet"). Returns None
    for anything that cannot be read unambiguously, including ranges, multiple
    quantities, comma-grouped numbers and unknown units.

    Args:
        dosage_text: Raw Prescription.dosage value (may be None).

    Returns:
        DosageAmount in canonical units, or None if the text is not parseable.
    """
    if not dosage_text or not isinstance(dosage_text, str):
        return None

    candidate = " ".join(dosage_text.strip().lower().split())
    match = _DOSAGE_PATTERN.match(candidate)
    if match is None:
        return None

    raw_value, raw_unit = match.groups()
    alias = _UNIT_ALIASES.get(raw_unit)
    if alias is None:
        return None

    canonical_unit, multiplier = alias
    try:
        value = float(raw_value)
    except ValueError:  # pragma: no cover - guarded by the pattern
        return None

    if value <= 0:
        return None

    return DosageAmount(
        value=value * multiplier,
        unit=canonical_unit,
        original=dosage_text.strip(),
    )


def _build_limit_index() -> Dict[str, DosageLimit]:
    """
    Builds the medication -> ceiling lookup from the curated dataset.

    Returns:
        Mapping of normalized medication name to its configured ceiling.

    Raises:
        ValueError: If the dataset contains an invalid or duplicated definition.
    """
    index: Dict[str, DosageLimit] = {}

    for medication, max_dose, unit, severity, note in _DOSAGE_LIMIT_DEFINITIONS:
        normalized = normalize_medication_name(medication)
        if not normalized or max_dose <= 0 or unit not in {"mg", "ml", "iu", "tablet"}:
            raise ValueError(f"Invalid dosage limit definition for: {medication}")
        if normalized in index:
            raise ValueError(f"Duplicate dosage limit definition for: {normalized}")

        index[normalized] = DosageLimit(
            medication=normalized,
            max_single_dose=max_dose,
            unit=unit,
            severity=severity,
            note=note,
        )

    return index


# Immutable index built once at import time; lookups are pure dictionary reads.
_DOSAGE_LIMIT_INDEX: Dict[str, DosageLimit] = _build_limit_index()


def get_dosage_limit(medication_name: Optional[str]) -> Optional[DosageLimit]:
    """
    Returns the configured single-dose ceiling for a medication, if one exists.
    """
    normalized = normalize_medication_name(medication_name)
    if not normalized:
        return None
    return _DOSAGE_LIMIT_INDEX.get(normalized)


def check_dosage(
    medication_name: Optional[str],
    dosage_text: Optional[str],
) -> Optional[DosageExceedance]:
    """
    Checks whether a prescribed dose exceeds its configured ceiling.

    Returns None - meaning "no concern detected" or "cannot be evaluated" -
    when any of the following holds, so an unreadable dose is never reported as
    unsafe:
    - the medication has no configured ceiling,
    - the dosage text cannot be parsed,
    - the parsed unit is not comparable with the ceiling's unit
      (for example "1 tablet" against a milligram ceiling),
    - the dose is at or below the ceiling.

    Args:
        medication_name: Medication name (raw or normalized).
        dosage_text: Raw Prescription.dosage value.

    Returns:
        DosageExceedance when the dose clearly exceeds the ceiling, else None.
    """
    limit = get_dosage_limit(medication_name)
    if limit is None:
        return None

    dose = parse_dosage(dosage_text)
    if dose is None or dose.unit != limit.unit:
        return None

    if dose.value <= limit.max_single_dose:
        return None

    return DosageExceedance(
        medication=limit.medication,
        dose=dose,
        limit=limit,
        severity=limit.severity,
        description=(
            f"A single dose of {_format_amount(dose.value, dose.unit)} was recorded, "
            f"which is above the usual maximum single dose of "
            f"{_format_amount(limit.max_single_dose, limit.unit)}. {limit.note}"
        ),
    )


def is_dosage_evaluable(
    medication_name: Optional[str],
    dosage_text: Optional[str],
) -> bool:
    """
    Returns True if a dose can actually be compared against a configured ceiling.

    Useful for distinguishing "checked and safe" from "could not be checked".
    """
    limit = get_dosage_limit(medication_name)
    if limit is None:
        return False

    dose = parse_dosage(dosage_text)
    return dose is not None and dose.unit == limit.unit


def get_known_dosage_limits() -> List[DosageLimit]:
    """
    Returns all configured dosage ceilings, ordered by medication name.

    Intended for introspection, documentation and testing.
    """
    return [_DOSAGE_LIMIT_INDEX[name] for name in sorted(_DOSAGE_LIMIT_INDEX)]


def _format_amount(value: float, unit: str) -> str:
    """
    Formats a canonical amount for display, dropping a redundant decimal part.
    """
    rendered = f"{value:.2f}".rstrip("0").rstrip(".")
    if unit == "tablet":
        return f"{rendered} tablet" if rendered == "1" else f"{rendered} tablets"
    return f"{rendered} {unit}"
