import unittest

from app.services.medication_interactions import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    MedicationInteraction,
    check_interaction,
    get_known_interactions,
    has_interaction,
    normalize_medication_name,
)


class MedicationNameNormalizationTestCase(unittest.TestCase):
    """
    Unit tests for the medication name normalization used by all lookups.
    """

    def test_lowercases_and_strips(self):
        """Names are reduced to their canonical lowercase form."""
        self.assertEqual(normalize_medication_name("Warfarin"), "warfarin")
        self.assertEqual(normalize_medication_name("  WARFARIN  "), "warfarin")

    def test_matches_the_persistence_normalization_rule(self):
        """
        Normalization agrees with MedicalPersistenceService, which stores
        (normalized_name or name).strip().lower().
        """
        for raw in ("Warfarin", " Aspirin ", "METFORMIN"):
            with self.subTest(raw=raw):
                self.assertEqual(
                    normalize_medication_name(raw), raw.strip().lower()
                )

    def test_removes_punctuation_and_collapses_whitespace(self):
        """Formatting differences do not prevent a match."""
        self.assertEqual(normalize_medication_name("Aspirin."), "aspirin")
        self.assertEqual(normalize_medication_name("Amoxi-cillin (500mg)"), "amoxi-cillin 500mg")
        self.assertEqual(normalize_medication_name("Vitamin   D"), "vitamin d")

    def test_empty_and_invalid_input_returns_empty_string(self):
        """Missing or non-string input is handled without raising."""
        for value in (None, "", "   ", 123, [], {}):
            with self.subTest(value=value):
                self.assertEqual(normalize_medication_name(value), "")

    def test_is_idempotent(self):
        """Normalizing an already normalized name changes nothing."""
        once = normalize_medication_name("Amoxi-cillin (500mg)")
        self.assertEqual(normalize_medication_name(once), once)


class InteractionDatasetTestCase(unittest.TestCase):
    """
    Unit tests for the integrity of the curated interaction dataset.
    """

    def test_dataset_is_not_empty(self):
        """The engine ships with a usable set of interactions."""
        self.assertGreater(len(get_known_interactions()), 0)

    def test_no_duplicate_pairs(self):
        """Each medication pair is defined exactly once."""
        interactions = get_known_interactions()
        pairs = {(i.medication_a, i.medication_b) for i in interactions}
        self.assertEqual(len(pairs), len(interactions))

    def test_no_duplicate_directional_definitions(self):
        """
        A pair is never defined in both directions: keys are canonically sorted,
        so (a, b) and (b, a) cannot both exist.
        """
        for interaction in get_known_interactions():
            with self.subTest(pair=(interaction.medication_a, interaction.medication_b)):
                self.assertLess(interaction.medication_a, interaction.medication_b)

    def test_every_entry_is_well_formed(self):
        """Names are normalized, distinct, and carry a description."""
        for interaction in get_known_interactions():
            with self.subTest(pair=(interaction.medication_a, interaction.medication_b)):
                self.assertTrue(interaction.medication_a)
                self.assertTrue(interaction.medication_b)
                self.assertNotEqual(interaction.medication_a, interaction.medication_b)
                self.assertEqual(
                    interaction.medication_a,
                    normalize_medication_name(interaction.medication_a),
                )
                self.assertEqual(
                    interaction.medication_b,
                    normalize_medication_name(interaction.medication_b),
                )
                self.assertTrue(interaction.description.strip())

    def test_severity_values_are_valid(self):
        """Severities stay within the risk vocabulary shared with Finding.risk_level."""
        allowed = {SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH}
        self.assertEqual(allowed, {"low", "medium", "high"})
        for interaction in get_known_interactions():
            with self.subTest(pair=(interaction.medication_a, interaction.medication_b)):
                self.assertIn(interaction.severity, allowed)

    def test_listing_is_ordered_and_stable(self):
        """The dataset listing is deterministic across calls."""
        first = get_known_interactions()
        second = get_known_interactions()
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            sorted(first, key=lambda i: (i.medication_a, i.medication_b)),
        )

    def test_listing_is_defensive_against_caller_mutation(self):
        """Mutating the returned list does not corrupt the internal index."""
        listing = get_known_interactions()
        original_length = len(listing)
        listing.clear()
        self.assertEqual(len(get_known_interactions()), original_length)

    def test_records_are_immutable(self):
        """An interaction record cannot be modified in place."""
        interaction = get_known_interactions()[0]
        with self.assertRaises(AttributeError):
            interaction.severity = "low"


class InteractionLookupTestCase(unittest.TestCase):
    """
    Unit tests for looking up a known interaction between two medications.
    """

    def test_known_pair_is_detected(self):
        """A curated pair returns its interaction record."""
        interaction = check_interaction("warfarin", "aspirin")

        self.assertIsInstance(interaction, MedicationInteraction)
        self.assertEqual(interaction.severity, SEVERITY_HIGH)
        self.assertIn("bleeding", interaction.description.lower())

    def test_lookup_is_direction_independent(self):
        """check_interaction(a, b) and check_interaction(b, a) agree."""
        for name_a, name_b in [
            ("warfarin", "aspirin"),
            ("simvastatin", "clarithromycin"),
            ("digoxin", "furosemide"),
        ]:
            with self.subTest(pair=(name_a, name_b)):
                forward = check_interaction(name_a, name_b)
                reverse = check_interaction(name_b, name_a)
                self.assertIsNotNone(forward)
                self.assertEqual(forward, reverse)

    def test_every_dataset_entry_resolves_in_both_directions(self):
        """No curated pair is reachable from only one direction."""
        for interaction in get_known_interactions():
            with self.subTest(pair=(interaction.medication_a, interaction.medication_b)):
                forward = check_interaction(
                    interaction.medication_a, interaction.medication_b
                )
                reverse = check_interaction(
                    interaction.medication_b, interaction.medication_a
                )
                self.assertEqual(forward, interaction)
                self.assertEqual(reverse, interaction)

    def test_lookup_normalizes_input(self):
        """Raw, messy names still resolve to the same interaction."""
        expected = check_interaction("warfarin", "aspirin")
        for name_a, name_b in [
            ("Warfarin", "Aspirin"),
            ("  WARFARIN  ", "aspirin."),
            ("Aspirin,", " Warfarin "),
        ]:
            with self.subTest(pair=(name_a, name_b)):
                self.assertEqual(check_interaction(name_a, name_b), expected)

    def test_unknown_pair_returns_none(self):
        """Medications with no curated interaction are not flagged."""
        self.assertIsNone(check_interaction("paracetamol", "vitamin d"))
        self.assertIsNone(check_interaction("warfarin", "paracetamol"))

    def test_same_medication_returns_none(self):
        """A medication is never reported as interacting with itself."""
        self.assertIsNone(check_interaction("warfarin", "warfarin"))
        self.assertIsNone(check_interaction("Warfarin", " warfarin "))

    def test_empty_or_missing_names_return_none(self):
        """Missing input never produces an interaction."""
        for name_a, name_b in [
            (None, None),
            (None, "aspirin"),
            ("warfarin", None),
            ("", "aspirin"),
            ("warfarin", ""),
            ("   ", "aspirin"),
            (123, "aspirin"),
        ]:
            with self.subTest(pair=(name_a, name_b)):
                self.assertIsNone(check_interaction(name_a, name_b))

    def test_has_interaction_matches_check_interaction(self):
        """The boolean helper agrees with the full lookup."""
        self.assertTrue(has_interaction("warfarin", "aspirin"))
        self.assertTrue(has_interaction("Aspirin", "Warfarin"))
        self.assertFalse(has_interaction("warfarin", "paracetamol"))
        self.assertFalse(has_interaction("warfarin", "warfarin"))
        self.assertFalse(has_interaction(None, "aspirin"))

    def test_repeated_lookups_are_deterministic(self):
        """The same inputs always produce the same result."""
        for _ in range(3):
            self.assertEqual(
                check_interaction("Warfarin", "Aspirin"),
                check_interaction("aspirin", "warfarin"),
            )
        self.assertIsNone(check_interaction("paracetamol", "vitamin d"))


if __name__ == "__main__":
    unittest.main()
