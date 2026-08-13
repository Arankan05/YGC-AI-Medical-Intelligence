import io
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Union

from PIL import Image, UnidentifiedImageError
import pymupdf
import pytesseract

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Base exception for all OCR-related errors."""
    pass


class InvalidImageError(OCRError):
    """Raised when image bytes or objects are empty, malformed, or unreadable."""
    pass


class InvalidPDFError(OCRError):
    """Raised when PDF bytes are empty, malformed, encrypted, or cannot be opened."""
    pass


class TesseractNotFoundError(OCRError):
    """Raised when the Tesseract OCR executable cannot be found or executed."""
    pass


@dataclass(frozen=True)
class ImageOCRResult:
    """
    Structured result of OCR performed on an individual image.

    Attributes:
        extracted_text: Text extracted by OCR from the image.
        confidence: Average confidence score (0.0 to 100.0) across detected words, or None if unavailable.
    """
    extracted_text: str
    confidence: Optional[float] = None


@dataclass(frozen=True)
class PDFOCRResult:
    """
    Structured result of OCR performed on a multi-page or single-page PDF document.

    Attributes:
        extracted_text: Complete extracted OCR text formatted with clear page boundaries.
        page_count: Total number of pages in the PDF document.
        has_text: True if OCR detected non-empty text on at least one page, False otherwise.
        page_texts: List of extracted text strings per page.
        average_confidence: Average OCR confidence across all pages with text, or None if unavailable.
    """
    extracted_text: str
    page_count: int
    has_text: bool
    page_texts: List[str] = field(default_factory=list)
    average_confidence: Optional[float] = None


class OCRService:
    """
    Modular OCR service for extracting text from images and scanned PDF documents using Tesseract.
    Independent of web frameworks, HTTP requests, and database layers for pipeline reuse.
    """

    DEFAULT_DPI: int = 200

    def __init__(self, tesseract_cmd: Optional[str] = None, default_dpi: int = DEFAULT_DPI):
        """
        Initialize the OCR service and configure the Tesseract executable path.

        Args:
            tesseract_cmd: Optional explicit path to the tesseract executable.
                           If not provided, resolves from TESSERACT_CMD environment variable / Settings.
            default_dpi: Rendering DPI for converting PDF pages to raster images (default 200).
        """
        self.default_dpi = default_dpi
        self._configure_tesseract(tesseract_cmd)

    def _configure_tesseract(self, explicit_cmd: Optional[str] = None) -> None:
        """
        Resolves and configures the Tesseract binary location.
        Prefers explicit path, then TESSERACT_CMD env variable / Settings, then falls back to system PATH.
        """
        cmd = explicit_cmd
        if not cmd:
            cmd = os.environ.get("TESSERACT_CMD")
        if not cmd:
            try:
                settings = get_settings()
                cmd = settings.TESSERACT_CMD
            except Exception:
                cmd = None

        if cmd and cmd.strip():
            pytesseract.pytesseract.tesseract_cmd = cmd.strip()
            logger.debug("Tesseract executable configured from environment/settings.")
        else:
            logger.debug("Tesseract executable defaulting to system PATH lookup.")

    def _calculate_confidence(self, ocr_data: dict) -> Optional[float]:
        """
        Calculates the average confidence score (0.0 to 100.0) from pytesseract word data.
        """
        conf_scores: List[float] = []
        conf_list = ocr_data.get("conf", [])
        text_list = ocr_data.get("text", [])

        for conf, text in zip(conf_list, text_list):
            try:
                c = float(conf)
                # Tesseract uses -1 for block/paragraph headers; only include valid words
                if c >= 0 and str(text).strip():
                    conf_scores.append(c)
            except (ValueError, TypeError):
                continue

        if conf_scores:
            return round(sum(conf_scores) / len(conf_scores), 2)
        return None

    def extract_from_image(self, image_input: Union[Image.Image, bytes]) -> ImageOCRResult:
        """
        Performs OCR text extraction on an image object or raw image bytes.

        Args:
            image_input: PIL Image instance or raw image bytes (PNG, JPEG, TIFF, etc.).

        Returns:
            ImageOCRResult containing extracted text and confidence.

        Raises:
            InvalidImageError: If image_input is empty, invalid, or corrupted.
            TesseractNotFoundError: If Tesseract executable is missing.
            OCRError: If an unexpected error occurs during OCR processing.
        """
        if image_input is None:
            raise InvalidImageError("Image input cannot be None.")

        img: Optional[Image.Image] = None
        should_close = False

        try:
            if isinstance(image_input, bytes):
                if len(image_input) == 0:
                    raise InvalidImageError("Image bytes cannot be empty.")
                try:
                    img = Image.open(io.BytesIO(image_input))
                    should_close = True
                except (UnidentifiedImageError, Exception) as img_err:
                    logger.error("Failed to decode image from provided bytes: %s", type(img_err).__name__)
                    raise InvalidImageError("Provided bytes do not represent a readable image.") from img_err
            elif isinstance(image_input, Image.Image):
                img = image_input
            else:
                raise InvalidImageError(f"Unsupported image input type: {type(image_input).__name__}")

            # Verify image has dimensions
            if img.width <= 0 or img.height <= 0:
                raise InvalidImageError("Image has invalid dimensions.")

            # Perform OCR text extraction
            try:
                raw_text = pytesseract.image_to_string(img)
                extracted_text = raw_text.strip() if raw_text else ""
            except (pytesseract.TesseractNotFoundError, FileNotFoundError) as t_err:
                logger.error("Tesseract executable not found or inaccessible: %s", type(t_err).__name__)
                raise TesseractNotFoundError("Tesseract OCR executable was not found. Configure TESSERACT_CMD or verify system PATH.") from t_err
            except pytesseract.TesseractError as t_err:
                logger.error("Tesseract processing failed: %s", str(t_err))
                raise OCRError(f"Tesseract OCR processing failed: {t_err}") from t_err
            except Exception as e:
                logger.error("Unexpected error during image OCR text extraction: %s", type(e).__name__)
                raise OCRError(f"OCR processing failed: {type(e).__name__}") from e

            # Extract confidence data
            confidence: Optional[float] = None
            try:
                ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                confidence = self._calculate_confidence(ocr_data)
            except Exception as conf_err:
                logger.warning("Could not calculate OCR confidence score: %s", type(conf_err).__name__)

            return ImageOCRResult(
                extracted_text=extracted_text,
                confidence=confidence,
            )

        finally:
            if should_close and img is not None:
                try:
                    img.close()
                except Exception as close_err:
                    logger.warning("Error closing PIL image: %s", type(close_err).__name__)

    def extract_from_pdf(self, pdf_bytes: bytes, dpi: Optional[int] = None) -> PDFOCRResult:
        """
        Renders each page of a PDF document into an image at the specified DPI and performs OCR page-by-page.

        Args:
            pdf_bytes: Raw binary content of the PDF document.
            dpi: Resolution DPI for page rasterization (defaults to service's default_dpi, e.g. 200).

        Returns:
            PDFOCRResult with extracted_text, page_count, has_text, page_texts, and average_confidence.

        Raises:
            InvalidPDFError: If pdf_bytes is empty, corrupt, encrypted, or not a readable PDF.
            TesseractNotFoundError: If Tesseract executable is missing.
            OCRError: If an error occurs during OCR processing.
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise InvalidPDFError("Cannot perform OCR on empty PDF bytes.")

        render_dpi = dpi if dpi is not None else self.default_dpi
        doc: Optional[pymupdf.Document] = None

        try:
            try:
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            except Exception as e:
                logger.error("Failed to open PDF document stream for OCR: %s", type(e).__name__)
                raise InvalidPDFError("Provided bytes do not represent a valid or readable PDF document.") from e

            if doc.is_closed:
                raise InvalidPDFError("PDF document stream could not be initialized.")

            if doc.is_encrypted:
                logger.warning("Encrypted PDF document detected during OCR attempt.")
                if not doc.authenticate(""):
                    raise InvalidPDFError("PDF document is password-protected and cannot be decrypted.")

            page_count = len(doc)
            if page_count == 0:
                return PDFOCRResult(
                    extracted_text="",
                    page_count=0,
                    has_text=False,
                    page_texts=[],
                    average_confidence=None,
                )

            page_texts: List[str] = []
            page_confidences: List[float] = []

            for page_index in range(page_count):
                page_img: Optional[Image.Image] = None
                try:
                    page = doc[page_index]
                    pix = page.get_pixmap(dpi=render_dpi)
                    pix_bytes = pix.tobytes("png")
                    page_img = Image.open(io.BytesIO(pix_bytes))

                    img_result = self.extract_from_image(page_img)
                    page_texts.append(img_result.extracted_text)

                    if img_result.confidence is not None:
                        page_confidences.append(img_result.confidence)

                except (TesseractNotFoundError, InvalidPDFError):
                    raise
                except Exception as page_err:
                    logger.warning("Error performing OCR on page %d: %s", page_index + 1, type(page_err).__name__)
                    page_texts.append("")
                finally:
                    if page_img is not None:
                        try:
                            page_img.close()
                        except Exception:
                            pass

            # Format extracted text with clear page boundaries
            formatted_pages: List[str] = []
            for i, p_text in enumerate(page_texts, start=1):
                if p_text:
                    formatted_pages.append(f"--- Page {i} ---\n{p_text}")
                else:
                    formatted_pages.append(f"--- Page {i} ---")

            full_extracted_text = "\n\n".join(formatted_pages)

            # Determine whether any meaningful text was extracted
            combined_raw = "".join(page_texts).strip()
            has_text = len(combined_raw) > 0

            avg_conf: Optional[float] = None
            if page_confidences:
                avg_conf = round(sum(page_confidences) / len(page_confidences), 2)

            return PDFOCRResult(
                extracted_text=full_extracted_text,
                page_count=page_count,
                has_text=has_text,
                page_texts=page_texts,
                average_confidence=avg_conf,
            )

        except (OCRError,):
            raise
        except Exception as e:
            logger.error("Unexpected error during PDF OCR extraction: %s", type(e).__name__)
            raise OCRError(f"Unexpected error during PDF OCR extraction: {type(e).__name__}") from e
        finally:
            if doc is not None and not doc.is_closed:
                try:
                    doc.close()
                except Exception as close_err:
                    logger.warning("Error closing PyMuPDF document after OCR: %s", type(close_err).__name__)


_default_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """
    Returns a shared singleton instance of OCRService.
    """
    global _default_ocr_service
    if _default_ocr_service is None:
        _default_ocr_service = OCRService()
    return _default_ocr_service


def extract_ocr_from_image(image_input: Union[Image.Image, bytes]) -> ImageOCRResult:
    """
    Convenience function to perform OCR on an image object or image bytes using default OCRService.
    """
    return get_ocr_service().extract_from_image(image_input)


def extract_ocr_from_pdf(pdf_bytes: bytes, dpi: Optional[int] = None) -> PDFOCRResult:
    """
    Convenience function to perform OCR on PDF bytes page-by-page using default OCRService.
    """
    return get_ocr_service().extract_from_pdf(pdf_bytes, dpi=dpi)
