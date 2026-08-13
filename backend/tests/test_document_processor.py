import unittest
from unittest.mock import MagicMock, patch
import pymupdf

from app.services.document_processor import (
    DocumentProcessingError,
    DocumentProcessingResult,
    DocumentProcessor,
    process_document,
)
from app.services.ocr_service import (
    OCRService,
    PDFOCRResult,
)
from app.services.pdf_extractor import (
    InvalidPDFError,
    PDFExtractionResult,
    PyMuPDFExtractor,
)


def create_in_memory_text_pdf(pages_text: list[str]) -> bytes:
    """Helper to create a PDF with a selectable text layer."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_in_memory_blank_pdf(page_count: int = 1) -> bytes:
    """Helper to create a PDF with empty pages (no selectable text)."""
    doc = pymupdf.open()
    for _ in range(page_count):
        doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class DocumentProcessorTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_pdf_extractor = MagicMock(spec=PyMuPDFExtractor)
        self.mock_ocr_service = MagicMock(spec=OCRService)
        self.processor = DocumentProcessor(
            pdf_extractor=self.mock_pdf_extractor,
            ocr_service=self.mock_ocr_service,
        )

    def test_text_pdf_chooses_pymupdf_and_does_not_call_ocr(self):
        """Test that when selectable text is present, PyMuPDF is used and OCR is NOT invoked."""
        fake_pdf_bytes = b"%PDF-1.4 mock text pdf"
        self.mock_pdf_extractor.extract_text.return_value = PDFExtractionResult(
            extracted_text="--- Page 1 ---\nComplete Blood Count: Normal",
            page_count=1,
            has_text=True,
            page_texts=["Complete Blood Count: Normal"],
        )

        result = self.processor.process_document(fake_pdf_bytes)

        self.mock_pdf_extractor.extract_text.assert_called_once_with(fake_pdf_bytes)
        self.mock_ocr_service.extract_from_pdf.assert_not_called()

        self.assertIsInstance(result, DocumentProcessingResult)
        self.assertEqual(result.extraction_method, "pymupdf")
        self.assertTrue(result.has_text)
        self.assertEqual(result.page_count, 1)
        self.assertIn("Complete Blood Count", result.extracted_text)
        self.assertIsNone(result.confidence)

    def test_scanned_pdf_without_selectable_text_falls_back_to_tesseract(self):
        """Test that when selectable text is missing (has_text=False), OCR is called."""
        fake_pdf_bytes = b"%PDF-1.4 mock scanned pdf"
        self.mock_pdf_extractor.extract_text.return_value = PDFExtractionResult(
            extracted_text="--- Page 1 ---",
            page_count=1,
            has_text=False,
            page_texts=[""],
        )
        self.mock_ocr_service.extract_from_pdf.return_value = PDFOCRResult(
            extracted_text="--- Page 1 ---\nScanned Lab Report: Glucose 110",
            page_count=1,
            has_text=True,
            page_texts=["Scanned Lab Report: Glucose 110"],
            average_confidence=92.5,
        )

        result = self.processor.process_document(fake_pdf_bytes)

        self.mock_pdf_extractor.extract_text.assert_called_once_with(fake_pdf_bytes)
        self.mock_ocr_service.extract_from_pdf.assert_called_once_with(fake_pdf_bytes)

        self.assertIsInstance(result, DocumentProcessingResult)
        self.assertEqual(result.extraction_method, "tesseract")
        self.assertTrue(result.has_text)
        self.assertEqual(result.page_count, 1)
        self.assertIn("Scanned Lab Report", result.extracted_text)
        self.assertEqual(result.confidence, 92.5)

    def test_blank_pdf_both_empty_returns_tesseract_with_has_text_false(self):
        """Test that a completely blank document falls back to OCR and returns has_text=False."""
        fake_pdf_bytes = b"%PDF-1.4 mock blank pdf"
        self.mock_pdf_extractor.extract_text.return_value = PDFExtractionResult(
            extracted_text="--- Page 1 ---\n--- Page 2 ---",
            page_count=2,
            has_text=False,
            page_texts=["", ""],
        )
        self.mock_ocr_service.extract_from_pdf.return_value = PDFOCRResult(
            extracted_text="--- Page 1 ---\n--- Page 2 ---",
            page_count=2,
            has_text=False,
            page_texts=["", ""],
            average_confidence=None,
        )

        result = self.processor.process_document(fake_pdf_bytes)

        self.mock_pdf_extractor.extract_text.assert_called_once_with(fake_pdf_bytes)
        self.mock_ocr_service.extract_from_pdf.assert_called_once_with(fake_pdf_bytes)

        self.assertEqual(result.extraction_method, "tesseract")
        self.assertFalse(result.has_text)
        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.confidence, None)

    def test_empty_bytes_raises_invalid_pdf_error_without_calling_extractors(self):
        """Test that empty bytes directly raise InvalidPDFError without invoking extractors."""
        with self.assertRaises(InvalidPDFError):
            self.processor.process_document(b"")

        self.mock_pdf_extractor.extract_text.assert_not_called()
        self.mock_ocr_service.extract_from_pdf.assert_not_called()

    def test_corrupt_pdf_propagates_invalid_pdf_error_without_calling_ocr(self):
        """Test that corrupt PDFs raise InvalidPDFError from PyMuPDF and do NOT call OCR."""
        fake_corrupt_bytes = b"Corrupted non-pdf data"
        self.mock_pdf_extractor.extract_text.side_effect = InvalidPDFError("Corrupted PDF stream")

        with self.assertRaises(InvalidPDFError):
            self.processor.process_document(fake_corrupt_bytes)

        self.mock_pdf_extractor.extract_text.assert_called_once_with(fake_corrupt_bytes)
        self.mock_ocr_service.extract_from_pdf.assert_not_called()

    def test_real_text_pdf_integration(self):
        """Integration test with real in-memory text-based PDF using real services."""
        real_processor = DocumentProcessor()
        text_content = "Patient Name: Jane Doe\nDiagnosis: Hypertension"
        pdf_bytes = create_in_memory_text_pdf([text_content])

        result = real_processor.process_document(pdf_bytes)

        self.assertEqual(result.extraction_method, "pymupdf")
        self.assertTrue(result.has_text)
        self.assertEqual(result.page_count, 1)
        self.assertIn("Jane Doe", result.extracted_text)
        self.assertIn("Hypertension", result.extracted_text)

    def test_convenience_function_process_document(self):
        """Test module-level convenience function process_document."""
        text_content = "Clinical Laboratory Examination Report"
        pdf_bytes = create_in_memory_text_pdf([text_content])

        result = process_document(pdf_bytes)

        self.assertIsInstance(result, DocumentProcessingResult)
        self.assertEqual(result.extraction_method, "pymupdf")
        self.assertTrue(result.has_text)
        self.assertIn("Clinical Laboratory", result.extracted_text)


if __name__ == "__main__":
    unittest.main()
