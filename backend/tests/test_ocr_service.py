import io
import unittest
from PIL import Image, ImageDraw, ImageFont
import pymupdf

from app.services.ocr_service import (
    ImageOCRResult,
    InvalidImageError,
    InvalidPDFError,
    OCRError,
    OCRService,
    PDFOCRResult,
    TesseractNotFoundError,
    extract_ocr_from_image,
    extract_ocr_from_pdf,
)


def _get_test_font(size: int = 24) -> ImageFont.ImageFont:
    """Returns a readable PIL font for test image generation."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def create_in_memory_image_bytes(text: str = "Patient Test\nHemoglobin 13.5", width: int = 500, height: int = 150) -> bytes:
    """Helper to generate an in-memory PNG image containing specified text."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _get_test_font(size=24)
    draw.text((20, 20), text, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def create_in_memory_scanned_pdf(pages_text: list[str]) -> bytes:
    """Helper to generate a PDF simulating scanned document pages containing text."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=500, height=200)
        if text:
            # Draw text into page so rasterizer converts it to a clean scanned-like page
            page.insert_text((30, 60), text, fontsize=16)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class OCRServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = OCRService()

    def test_extract_valid_image_bytes(self):
        """Test OCR extraction from valid synthetic image bytes."""
        image_bytes = create_in_memory_image_bytes("Patient Test\nHemoglobin 13.5")
        result = self.service.extract_from_image(image_bytes)

        self.assertIsInstance(result, ImageOCRResult)
        self.assertIn("Patient", result.extracted_text)
        self.assertIn("Hemoglobin", result.extracted_text)
        self.assertIsNotNone(result.confidence)
        if result.confidence is not None:
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 100.0)

    def test_extract_valid_pil_image_object(self):
        """Test OCR extraction when passing a PIL Image instance directly."""
        img = Image.new("RGB", (500, 150), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        font = _get_test_font(size=24)
        draw.text((20, 20), "Blood Glucose 95", fill=(0, 0, 0), font=font)

        result = self.service.extract_from_image(img)
        img.close()

        self.assertIsInstance(result, ImageOCRResult)
        self.assertIn("Glucose", result.extracted_text)

    def test_extract_convenience_function_image(self):
        """Test extract_ocr_from_image module-level helper."""
        image_bytes = create_in_memory_image_bytes("Lab Report Normal")
        result = extract_ocr_from_image(image_bytes)

        self.assertIsInstance(result, ImageOCRResult)
        self.assertIn("Lab Report", result.extracted_text)

    def test_empty_image_bytes_raises_invalid_image_error(self):
        """Test empty image bytes raises InvalidImageError."""
        with self.assertRaises(InvalidImageError):
            self.service.extract_from_image(b"")

        with self.assertRaises(InvalidImageError):
            extract_ocr_from_image(b"")

    def test_corrupted_image_bytes_raises_invalid_image_error(self):
        """Test invalid/corrupt image bytes raises InvalidImageError."""
        corrupt_bytes = b"Not a real image file content"
        with self.assertRaises(InvalidImageError):
            self.service.extract_from_image(corrupt_bytes)

    def test_extract_valid_single_page_pdf(self):
        """Test OCR on a valid single-page PDF document."""
        pdf_bytes = create_in_memory_scanned_pdf(["Patient Blood Test\nNormal hemoglobin levels."])
        result = self.service.extract_from_pdf(pdf_bytes)

        self.assertIsInstance(result, PDFOCRResult)
        self.assertEqual(result.page_count, 1)
        self.assertTrue(result.has_text)
        self.assertIn("--- Page 1 ---", result.extracted_text)
        self.assertIn("Patient", result.extracted_text)
        self.assertEqual(len(result.page_texts), 1)
        self.assertIsNotNone(result.average_confidence)

    def test_extract_multi_page_pdf_preserves_boundaries(self):
        """Test multi-page PDF OCR preserves page boundaries and page counts."""
        page1 = "Prescription Amoxicillin 500mg"
        page2 = "Lab Results WBC 6.5 RBC 4.8"
        page3 = "Doctor Notes Patient recovering well"

        pdf_bytes = create_in_memory_scanned_pdf([page1, page2, page3])
        result = extract_ocr_from_pdf(pdf_bytes)

        self.assertEqual(result.page_count, 3)
        self.assertTrue(result.has_text)
        self.assertEqual(len(result.page_texts), 3)

        self.assertIn("--- Page 1 ---", result.extracted_text)
        self.assertIn("Amoxicillin", result.extracted_text)
        self.assertIn("--- Page 2 ---", result.extracted_text)
        self.assertIn("WBC", result.extracted_text)
        self.assertIn("--- Page 3 ---", result.extracted_text)
        self.assertIn("recovering", result.extracted_text)

    def test_extract_blank_pdf_has_text_false(self):
        """Test PDF with blank pages returns has_text=False."""
        pdf_bytes = create_in_memory_scanned_pdf(["", ""])
        result = self.service.extract_from_pdf(pdf_bytes)

        self.assertEqual(result.page_count, 2)
        self.assertFalse(result.has_text)
        self.assertIn("--- Page 1 ---", result.extracted_text)
        self.assertIn("--- Page 2 ---", result.extracted_text)

    def test_empty_pdf_bytes_raises_invalid_pdf_error(self):
        """Test empty PDF bytes raises InvalidPDFError."""
        with self.assertRaises(InvalidPDFError):
            self.service.extract_from_pdf(b"")

        with self.assertRaises(InvalidPDFError):
            extract_ocr_from_pdf(b"")

    def test_corrupted_pdf_bytes_raises_invalid_pdf_error(self):
        """Test corrupt/invalid PDF bytes raises InvalidPDFError."""
        corrupt_bytes = b"%PDF-1.4 Corrupted content that cannot be parsed"
        with self.assertRaises(InvalidPDFError):
            self.service.extract_from_pdf(corrupt_bytes)

    def test_missing_tesseract_executable_raises_tesseract_not_found_error(self):
        """Test configured non-existent Tesseract path raises TesseractNotFoundError."""
        bad_service = OCRService(tesseract_cmd=r"C:\NonExistentDirectory\tesseract_fake.exe")
        image_bytes = create_in_memory_image_bytes("Test text")

        with self.assertRaises(TesseractNotFoundError):
            bad_service.extract_from_image(image_bytes)

        with self.assertRaises(TesseractNotFoundError):
            pdf_bytes = create_in_memory_scanned_pdf(["Test text"])
            bad_service.extract_from_pdf(pdf_bytes)


if __name__ == "__main__":
    unittest.main()
