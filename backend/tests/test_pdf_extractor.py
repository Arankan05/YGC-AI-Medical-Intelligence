import unittest
import pymupdf

from app.services.pdf_extractor import (
    InvalidPDFError,
    PDFExtractionError,
    PDFExtractionResult,
    PyMuPDFExtractor,
    extract_pdf_text,
)


def create_in_memory_pdf(pages_content: list[str]) -> bytes:
    """Helper to generate an in-memory PDF binary with specified page contents."""
    doc = pymupdf.open()
    for text in pages_content:
        page = doc.new_page()
        if text:
            page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class PDFExtractorTestCase(unittest.TestCase):
    def setUp(self):
        self.extractor = PyMuPDFExtractor()

    def test_extract_valid_single_page_pdf(self):
        """Test extraction of text from a valid single-page PDF."""
        sample_text = "Patient Blood Test Report: Normal hemoglobin levels."
        pdf_bytes = create_in_memory_pdf([sample_text])

        result = self.extractor.extract_text(pdf_bytes)

        self.assertIsInstance(result, PDFExtractionResult)
        self.assertEqual(result.page_count, 1)
        self.assertTrue(result.has_text)
        self.assertIn("Patient Blood Test Report", result.extracted_text)
        self.assertIn("--- Page 1 ---", result.extracted_text)
        self.assertEqual(len(result.page_texts), 1)
        self.assertIn("Patient Blood Test Report", result.page_texts[0])

    def test_extract_multi_page_pdf_preserves_boundaries(self):
        """Test multi-page PDF extracts text page-by-page and preserves boundaries."""
        page1 = "Prescription: Amoxicillin 500mg"
        page2 = "Lab Results: WBC 6.5, RBC 4.8"
        page3 = "Doctor Notes: Patient recovering well."

        pdf_bytes = create_in_memory_pdf([page1, page2, page3])
        result = extract_pdf_text(pdf_bytes)

        self.assertEqual(result.page_count, 3)
        self.assertTrue(result.has_text)
        self.assertEqual(len(result.page_texts), 3)

        self.assertIn("--- Page 1 ---", result.extracted_text)
        self.assertIn(page1, result.extracted_text)
        self.assertIn("--- Page 2 ---", result.extracted_text)
        self.assertIn(page2, result.extracted_text)
        self.assertIn("--- Page 3 ---", result.extracted_text)
        self.assertIn(page3, result.extracted_text)

    def test_extract_blank_page_pdf(self):
        """Test PDF with empty/blank pages returns has_text=False."""
        pdf_bytes = create_in_memory_pdf(["", "   "])
        result = self.extractor.extract_text(pdf_bytes)

        self.assertEqual(result.page_count, 2)
        self.assertFalse(result.has_text)
        self.assertEqual(result.page_texts, ["", ""])

    def test_empty_bytes_raises_invalid_pdf_error(self):
        """Test empty bytes raises InvalidPDFError."""
        with self.assertRaises(InvalidPDFError):
            self.extractor.extract_text(b"")

        with self.assertRaises(InvalidPDFError):
            extract_pdf_text(b"")

    def test_corrupted_or_invalid_pdf_bytes_raises_invalid_pdf_error(self):
        """Test non-PDF or corrupt binary bytes raise InvalidPDFError."""
        corrupt_bytes = b"This is plain text and definitely not a valid PDF header"
        with self.assertRaises(InvalidPDFError):
            self.extractor.extract_text(corrupt_bytes)

    def test_random_binary_garbage_raises_invalid_pdf_error(self):
        """Test arbitrary binary garbage raises InvalidPDFError."""
        garbage_bytes = b"\x00\x01\x02\x03\xff\xfe\xfd\xfa\xce\xde"
        with self.assertRaises(InvalidPDFError):
            self.extractor.extract_text(garbage_bytes)


if __name__ == "__main__":
    unittest.main()
