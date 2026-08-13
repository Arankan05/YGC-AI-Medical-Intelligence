import unittest

from app.services.text_cleaner import TextCleaner, clean_text


class TextCleanerTestCase(unittest.TestCase):
    """
    Unit tests for conservative, deterministic medical text cleaner.
    """

    def setUp(self):
        self.cleaner = TextCleaner()

    def test_empty_string_returns_empty(self):
        """Empty string input returns empty string."""
        self.assertEqual(clean_text(""), "")
        self.assertEqual(self.cleaner.clean(""), "")

    def test_none_input_returns_empty(self):
        """None input safely returns empty string without error."""
        self.assertEqual(clean_text(None), "")
        self.assertEqual(self.cleaner.clean(None), "")

    def test_whitespace_only_returns_empty(self):
        """Whitespace-only strings (spaces, tabs, newlines) return empty string."""
        self.assertEqual(clean_text("   "), "")
        self.assertEqual(clean_text("\t\t\n  \r\n  "), "")
        self.assertEqual(clean_text("\n\n\n"), "")

    def test_crlf_normalization(self):
        """Windows CRLF (\\r\\n) is normalized to standard Unix LF (\\n)."""
        raw = "Line 1\r\nLine 2\r\nLine 3"
        expected = "Line 1\nLine 2\nLine 3"
        self.assertEqual(clean_text(raw), expected)

    def test_cr_normalization(self):
        """Legacy Mac CR (\\r) is normalized to standard Unix LF (\\n)."""
        raw = "Line 1\rLine 2\rLine 3"
        expected = "Line 1\nLine 2\nLine 3"
        self.assertEqual(clean_text(raw), expected)

    def test_mixed_line_endings_normalization(self):
        """Mixed line endings (\\r\\n, \\r, \\n) are all normalized to standard LF."""
        raw = "Line 1\r\nLine 2\rLine 3\nLine 4"
        expected = "Line 1\nLine 2\nLine 3\nLine 4"
        self.assertEqual(clean_text(raw), expected)

    def test_tab_normalization(self):
        """Tabs are normalized to standard spaces without altering adjacent tokens."""
        raw = "Patient Name:\tJohn Doe\tID:\t12345"
        expected = "Patient Name: John Doe ID: 12345"
        self.assertEqual(clean_text(raw), expected)

    def test_trailing_whitespace_removal(self):
        """Trailing whitespace on individual lines is stripped."""
        raw = "Header line    \nSecond line\t  \nThird line "
        expected = "Header line\nSecond line\nThird line"
        self.assertEqual(clean_text(raw), expected)

    def test_excessive_blank_lines_collapsed(self):
        """Three or more consecutive newlines are collapsed to at most two."""
        raw = "Paragraph 1\n\n\n\n\nParagraph 2\n\n\nParagraph 3"
        expected = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        self.assertEqual(clean_text(raw), expected)

    def test_redundant_horizontal_spaces_collapsed(self):
        """Multiple consecutive spaces within a line are collapsed to single spaces."""
        raw = "Hemoglobin:     13.5    g/dL"
        expected = "Hemoglobin: 13.5 g/dL"
        self.assertEqual(clean_text(raw), expected)

    def test_preservation_of_numbers_and_decimals(self):
        """Numerical digits and decimal points in lab values are strictly preserved."""
        raw = "Sodium: 138.5 mEq/L\nPotassium: 4.20 mEq/L\nChloride: 101 mEq/L"
        expected = "Sodium: 138.5 mEq/L\nPotassium: 4.20 mEq/L\nChloride: 101 mEq/L"
        self.assertEqual(clean_text(raw), expected)

    def test_preservation_of_medical_units(self):
        """Complex clinical unit notations are preserved without alteration."""
        raw = "WBC: 7.4 x 10^3/uL\nPlatelets: 250 x 10^3/mcL\nGlucose: 95 mg/dL\nCalcium: 2.35 mmol/L"
        expected = "WBC: 7.4 x 10^3/uL\nPlatelets: 250 x 10^3/mcL\nGlucose: 95 mg/dL\nCalcium: 2.35 mmol/L"
        self.assertEqual(clean_text(raw), expected)

    def test_preservation_of_medication_and_dosage(self):
        """Medication names, dosage quantities, frequencies, and instructions are preserved."""
        raw = "Rx: Amoxicillin 500 mg capsule\nSig: Take 1 cap PO TID x 10 days with food"
        expected = "Rx: Amoxicillin 500 mg capsule\nSig: Take 1 cap PO TID x 10 days with food"
        self.assertEqual(clean_text(raw), expected)

    def test_preservation_of_dates_and_reference_ranges(self):
        """Dates and reference ranges with symbols (<, >, -, /, :) are preserved."""
        raw = "Date of Service: 2026-08-14\neGFR: > 60.0 mL/min/1.73m2 (Ref: >= 60.0)"
        expected = "Date of Service: 2026-08-14\neGFR: > 60.0 mL/min/1.73m2 (Ref: >= 60.0)"
        self.assertEqual(clean_text(raw), expected)

    def test_preservation_of_page_headers_and_punctuation(self):
        """Page headers and complex clinical punctuation (hyphens, brackets, colons) are preserved."""
        raw = "--- Page 1 ---\nAssessment & Plan:\n1. Essential HTN (I10) - stable on Lisinopril 10mg daily."
        expected = "--- Page 1 ---\nAssessment & Plan:\n1. Essential HTN (I10) - stable on Lisinopril 10mg daily."
        self.assertEqual(clean_text(raw), expected)

    def test_no_spelling_or_ocr_character_alteration(self):
        """Does NOT alter character glyphs or attempt OCR error correction."""
        raw = "L1sinopril 1O mg daily"  # Contains OCR errors: '1' for 'i', 'O' for '0'
        # Conservative cleaning preserves raw characters exactly
        self.assertEqual(clean_text(raw), "L1sinopril 1O mg daily")

    def test_idempotence(self):
        """Cleaning an already cleaned text produces identical output: clean(clean(t)) == clean(t)."""
        samples = [
            "Patient Name:\tJohn Doe\r\n\r\n\r\nHemoglobin:   13.5 g/dL\r\nMedication: Amoxicillin 500 mg",
            "--- Page 1 ---\n\n\n\n\nBP: 120/80 mmHg\tHR: 72 bpm\r\n\r\nAssessment: Normal",
            "Sodium: 135 mEq/L (135 - 145)\nPotassium: 4.1 mEq/L",
            "   \t  \n  ",
            "Single line text",
        ]
        for sample in samples:
            first_pass = clean_text(sample)
            second_pass = clean_text(first_pass)
            self.assertEqual(first_pass, second_pass)

    def test_user_specification_example(self):
        """Tests the exact example from the project specifications."""
        raw = "Patient Name:\tJohn Doe\r\n\r\n\r\nHemoglobin:   13.5 g/dL\r\nMedication: Amoxicillin 500 mg"
        expected = "Patient Name: John Doe\n\nHemoglobin: 13.5 g/dL\nMedication: Amoxicillin 500 mg"
        self.assertEqual(clean_text(raw), expected)

    def test_custom_max_consecutive_newlines(self):
        """Custom TextCleaner with max_consecutive_newlines=1 collapses to single blank line."""
        custom_cleaner = TextCleaner(max_consecutive_newlines=1)
        raw = "Line 1\n\n\n\nLine 2"
        expected = "Line 1\nLine 2"
        self.assertEqual(custom_cleaner.clean(raw), expected)


if __name__ == "__main__":
    unittest.main()
