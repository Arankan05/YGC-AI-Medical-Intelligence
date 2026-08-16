import unittest

from app.services.medication_dosage_rules import (
    check_dosage,
    get_dosage_limit,
    get_known_dosage_limits,
    is_dosage_evaluable,
    parse_dosage,
)


class DosageParsingTestCase(unittest.TestCase):
    """
    Unit tests for the conservative, deterministic dosage string parser.
    """

    def test_parses_common_dosage_formats(self):
        """Simple numeric dosage strings are read correctly."""
        for text, expected in [
            ("500mg", 500.0),
            ("1000 mg", 1000.0),
            ("5 mg", 5.0),
            ("  250MG  ", 250.0),
            ("2.5 mg", 2.5),
        ]:
            with self.subTest(text=text):
                parsed = parse_dosage(text)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.value, expected)
                self.assertEqual(parsed.unit, "mg")

    def test_mass_units_are_converted_to_milligrams(self):
        """Grams and micrograms are canonicalised to milligrams."""
        self.assertEqual(parse_dosage("1 g").value, 1000.0)
        self.assertEqual(parse_dosage("1.5g").value, 1500.0)
        self.assertEqual(parse_dosage("500 mcg").value, 0.5)
        self.assertEqual(parse_dosage("500 micrograms").value, 0.5)

    def test_volume_and_count_units_are_recognised(self):
        """Millilitres and countable forms parse into their own unit families."""
        self.assertEqual(parse_dosage("10 ml").unit, "ml")
        self.assertEqual(parse_dosage("1 l").value, 1000.0)
        self.assertEqual(parse_dosage("1 tablet").unit, "tablet")
        self.assertEqual(parse_dosage("2 capsules").unit, "tablet")

    def test_original_text_is_preserved(self):
        """The raw string is kept for display alongside the parsed value."""
        self.assertEqual(parse_dosage(" 500mg ").original, "500mg")

    def test_unparseable_values_return_none(self):
        """Ambiguous or free-text dosages are not guessed at."""
        for text in [
            None,
            "",
            "   ",
            "as directed",
            "take two tablets",
            "500-1000mg",
            "500 mg - 1 g",
            "2 x 500mg",
            "1,000 mg",       # digit grouping is locale-dependent
            "500",            # no unit
            "mg",             # no number
            "500 puffs",      # unrecognised unit
            "0 mg",           # non-positive
            123,              # not a string
        ]:
            with self.subTest(text=text):
                self.assertIsNone(parse_dosage(text))


class DosageLimitTestCase(unittest.TestCase):
    """
    Unit tests for the curated single-dose ceiling dataset.
    """

    def test_dataset_is_well_formed(self):
        """Every configured ceiling is positive and uses a known unit."""
        limits = get_known_dosage_limits()

        self.assertGreater(len(limits), 0)
        self.assertEqual(len(limits), len({limit.medication for limit in limits}))
        for limit in limits:
            with self.subTest(medication=limit.medication):
                self.assertGreater(limit.max_single_dose, 0)
                self.assertIn(limit.unit, {"mg", "ml", "iu", "tablet"})
                self.assertIn(limit.severity, {"low", "medium", "high"})
                self.assertTrue(limit.note)

    def test_lookup_normalizes_medication_name(self):
        """Ceilings are found regardless of name formatting."""
        self.assertIsNotNone(get_dosage_limit("Paracetamol"))
        self.assertIsNotNone(get_dosage_limit("  PARACETAMOL  "))
        self.assertIsNone(get_dosage_limit("vitamin d"))
        self.assertIsNone(get_dosage_limit(None))


class DosageCheckTestCase(unittest.TestCase):
    """
    Unit tests for comparing a prescribed dose against its ceiling.
    """

    def test_dose_above_ceiling_is_flagged(self):
        """A dose clearly above the ceiling produces an exceedance."""
        exceedance = check_dosage("paracetamol", "1500mg")

        self.assertIsNotNone(exceedance)
        self.assertEqual(exceedance.medication, "paracetamol")
        self.assertEqual(exceedance.dose.value, 1500.0)
        self.assertEqual(exceedance.limit.max_single_dose, 1000.0)
        self.assertEqual(exceedance.severity, "high")
        self.assertIn("1500 mg", exceedance.description)
        self.assertIn("1000 mg", exceedance.description)

    def test_dose_above_ceiling_in_other_units_is_flagged(self):
        """Unit conversion is applied before comparison."""
        exceedance = check_dosage("paracetamol", "2 g")

        self.assertIsNotNone(exceedance)
        self.assertEqual(exceedance.dose.value, 2000.0)
        self.assertEqual(exceedance.dose.original, "2 g")

    def test_dose_at_or_below_ceiling_is_not_flagged(self):
        """Doses at or under the ceiling are safe."""
        self.assertIsNone(check_dosage("paracetamol", "500mg"))
        self.assertIsNone(check_dosage("paracetamol", "1000 mg"))
        self.assertIsNone(check_dosage("paracetamol", "1 g"))
        self.assertIsNone(check_dosage("ibuprofen", "400mg"))

    def test_unknown_medication_is_never_flagged(self):
        """Medications outside the dataset are not evaluated."""
        self.assertIsNone(check_dosage("vitamin d", "999999 mg"))

    def test_unparseable_dosage_is_never_flagged(self):
        """An unreadable dosage is never assumed to be unsafe."""
        for text in [None, "", "as directed", "500-1000mg", "1,000 mg", "lots"]:
            with self.subTest(text=text):
                self.assertIsNone(check_dosage("paracetamol", text))

    def test_mismatched_unit_family_is_never_flagged(self):
        """A dose in an incomparable unit is not evaluated."""
        self.assertIsNone(check_dosage("paracetamol", "5 tablets"))
        self.assertIsNone(check_dosage("paracetamol", "50 ml"))

    def test_is_dosage_evaluable(self):
        """Evaluability distinguishes 'checked and safe' from 'not checked'."""
        self.assertTrue(is_dosage_evaluable("paracetamol", "500mg"))
        self.assertTrue(is_dosage_evaluable("paracetamol", "5 g"))
        self.assertFalse(is_dosage_evaluable("paracetamol", "1 tablet"))
        self.assertFalse(is_dosage_evaluable("paracetamol", "as directed"))
        self.assertFalse(is_dosage_evaluable("vitamin d", "500mg"))

    def test_check_is_deterministic(self):
        """Repeated checks return identical results."""
        self.assertEqual(
            check_dosage("warfarin", "15mg"),
            check_dosage("Warfarin", "15mg"),
        )


if __name__ == "__main__":
    unittest.main()
