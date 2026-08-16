"""
Deterministic drug-drug interaction knowledge base for the Medication Safety
& Clinical Contraindication Engine.

Design Principles:
- Deterministic: Pure in-memory lookup over a curated dataset. The same pair of
  medication names always yields the same result.
- Offline: No database, AI provider, or external API is involved. Interactions
  are never invented or inferred at runtime.
- Direction-agnostic: Each interaction is declared exactly once. The lookup key
  is the alphabetically sorted pair of normalized names, so (a, b) and (b, a)
  resolve to the same rule.
- Consistent normalization: Names are normalized with the same rule used when
  medications are persisted (``(normalized_name or name).strip().lower()``),
  so the keys of this dataset match ``Medication.normalized_name`` values.

Severity values are intentionally limited to "low", "medium" and "high" so they
map directly onto ``Finding.risk_level`` without further translation.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"


@dataclass(frozen=True)
class MedicationInteraction:
    """
    A single known interaction between two medications.

    Attributes:
        medication_a: Normalized name of the first medication in the pair.
        medication_b: Normalized name of the second medication in the pair.
        severity: Clinical severity ("low", "medium" or "high").
        description: Plain-language explanation of the interaction risk.
    """
    medication_a: str
    medication_b: str
    severity: str
    description: str


# Curated interaction dataset.
#
# Each entry is declared once, in a single direction, as:
#     (medication_a, medication_b, severity, description)
#
# Names must be written in normalized form (lowercase generic ingredient name).
# Keep this list small, well-established and clinically uncontroversial; it is a
# safety screening aid, not a complete pharmacological reference.
_INTERACTION_DEFINITIONS: Tuple[Tuple[str, str, str, str], ...] = (
    (
        "warfarin",
        "aspirin",
        SEVERITY_HIGH,
        "Combined use significantly increases the risk of serious bleeding, "
        "as both medications impair blood clotting through different mechanisms.",
    ),
    (
        "warfarin",
        "ibuprofen",
        SEVERITY_HIGH,
        "NSAIDs such as ibuprofen increase bleeding risk and may raise the "
        "anticoagulant effect of warfarin, increasing the risk of haemorrhage.",
    ),
    (
        "warfarin",
        "ciprofloxacin",
        SEVERITY_MEDIUM,
        "Ciprofloxacin can potentiate the anticoagulant effect of warfarin, "
        "leading to an elevated INR and increased bleeding risk.",
    ),
    (
        "simvastatin",
        "clarithromycin",
        SEVERITY_HIGH,
        "Clarithromycin inhibits the metabolism of simvastatin, raising statin "
        "levels and the risk of muscle damage (myopathy and rhabdomyolysis).",
    ),
    (
        "sertraline",
        "tramadol",
        SEVERITY_HIGH,
        "Both medications increase serotonin activity; combined use raises the "
        "risk of serotonin syndrome and may lower the seizure threshold.",
    ),
    (
        "lisinopril",
        "spironolactone",
        SEVERITY_HIGH,
        "Both medications raise serum potassium; combined use can cause "
        "hyperkalaemia and associated cardiac arrhythmias.",
    ),
    (
        "lisinopril",
        "ibuprofen",
        SEVERITY_MEDIUM,
        "NSAIDs reduce the blood-pressure-lowering effect of ACE inhibitors and "
        "may impair kidney function when used together.",
    ),
    (
        "methotrexate",
        "trimethoprim",
        SEVERITY_HIGH,
        "Both medications are folate antagonists; combined use can cause severe "
        "bone marrow suppression.",
    ),
    (
        "clopidogrel",
        "omeprazole",
        SEVERITY_MEDIUM,
        "Omeprazole inhibits the activation of clopidogrel, which can reduce its "
        "antiplatelet protection against clotting events.",
    ),
    (
        "digoxin",
        "furosemide",
        SEVERITY_MEDIUM,
        "Furosemide-induced potassium loss increases sensitivity to digoxin and "
        "the risk of digoxin toxicity.",
    ),
    (
        "amlodipine",
        "simvastatin",
        SEVERITY_LOW,
        "Amlodipine raises simvastatin levels; doses above 20 mg of simvastatin "
        "increase the risk of muscle-related side effects.",
    ),
)

# Characters that carry no meaning for name matching (punctuation, dosage
# separators, etc.). Letters, digits, spaces and hyphens are preserved.
_NAME_CLEANUP_PATTERN = re.compile(r"[^a-z0-9\s-]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_medication_name(name: Optional[str]) -> str:
    """
    Normalizes a medication name into the canonical form used for lookups.

    The rule mirrors how medication names are stored by
    MedicalPersistenceService: lowercase and stripped. Punctuation is removed
    and internal whitespace collapsed so that minor formatting differences do
    not prevent a match.

    Args:
        name: Raw or already normalized medication name (may be None).

    Returns:
        Normalized medication name, or an empty string if the input is empty.
    """
    if not name or not isinstance(name, str):
        return ""

    normalized = _NAME_CLEANUP_PATTERN.sub(" ", name.strip().lower())
    return _WHITESPACE_PATTERN.sub(" ", normalized).strip()


def _build_interaction_index() -> Dict[Tuple[str, str], MedicationInteraction]:
    """
    Builds the direction-agnostic lookup index from the curated dataset.

    Returns:
        Mapping of alphabetically sorted normalized name pairs to interactions.

    Raises:
        ValueError: If the dataset contains an invalid or duplicated definition.
    """
    index: Dict[Tuple[str, str], MedicationInteraction] = {}

    for medication_a, medication_b, severity, description in _INTERACTION_DEFINITIONS:
        norm_a = normalize_medication_name(medication_a)
        norm_b = normalize_medication_name(medication_b)

        if not norm_a or not norm_b or norm_a == norm_b:
            raise ValueError(
                f"Invalid interaction definition: ({medication_a}, {medication_b})"
            )

        key = _interaction_key(norm_a, norm_b)
        if key in index:
            raise ValueError(
                f"Duplicate interaction definition for pair: {key[0]} / {key[1]}"
            )

        index[key] = MedicationInteraction(
            medication_a=key[0],
            medication_b=key[1],
            severity=severity,
            description=description,
        )

    return index


def _interaction_key(normalized_a: str, normalized_b: str) -> Tuple[str, str]:
    """
    Returns the order-independent lookup key for a pair of normalized names.
    """
    if normalized_a <= normalized_b:
        return (normalized_a, normalized_b)
    return (normalized_b, normalized_a)


# Immutable index built once at import time; lookups are pure dictionary reads.
_INTERACTION_INDEX: Dict[Tuple[str, str], MedicationInteraction] = _build_interaction_index()


def check_interaction(
    medication_a: Optional[str],
    medication_b: Optional[str],
) -> Optional[MedicationInteraction]:
    """
    Checks two medications for a known interaction.

    The check is direction-independent: check_interaction(a, b) and
    check_interaction(b, a) return the same result.

    Args:
        medication_a: Name of the first medication (raw or normalized).
        medication_b: Name of the second medication (raw or normalized).

    Returns:
        The matching MedicationInteraction, or None if the pair is not present
        in the dataset, if either name is empty, or if both names refer to the
        same medication.
    """
    norm_a = normalize_medication_name(medication_a)
    norm_b = normalize_medication_name(medication_b)

    if not norm_a or not norm_b or norm_a == norm_b:
        return None

    return _INTERACTION_INDEX.get(_interaction_key(norm_a, norm_b))


def has_interaction(
    medication_a: Optional[str],
    medication_b: Optional[str],
) -> bool:
    """
    Returns True if a known interaction exists between the two medications.
    """
    return check_interaction(medication_a, medication_b) is not None


def get_known_interactions() -> List[MedicationInteraction]:
    """
    Returns all known interactions, ordered deterministically by medication pair.

    Intended for introspection, documentation and testing.
    """
    return [_INTERACTION_INDEX[key] for key in sorted(_INTERACTION_INDEX)]
