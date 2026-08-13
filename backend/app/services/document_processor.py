import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.ocr_service import (
    OCRError,
    OCRService,
    PDFOCRResult,
    get_ocr_service,
)
from app.services.pdf_extractor import (
    InvalidPDFError,
    PDFExtractionError,
    PDFExtractionResult,
    PyMuPDFExtractor,
    extract_pdf_text,
)

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Base exception for errors during document text processing orchestration."""
    pass


@dataclass(frozen=True)
class DocumentProcessingResult:
    """
    Structured result of document text processing.

    Attributes:
        extracted_text: Complete extracted text formatted with page boundaries.
        page_count: Total number of pages in the document.
        extraction_method: Strategy used to extract text ("pymupdf" or "tesseract").
        has_text: True if non-empty text was extracted, False otherwise.
        page_texts: List of text strings extracted for each page.
        confidence: Average confidence score if OCR was used, or None for native PDF extraction.
    """
    extracted_text: str
    page_count: int
    extraction_method: str  # "pymupdf" | "tesseract"
    has_text: bool
    page_texts: List[str] = field(default_factory=list)
    confidence: Optional[float] = None


class DocumentProcessor:
    """
    Orchestration service that attempts native PDF text extraction via PyMuPDF first,
    and intelligently falls back to Tesseract OCR when no selectable text is found.
    """

    def __init__(
        self,
        pdf_extractor: Optional[PyMuPDFExtractor] = None,
        ocr_service: Optional[OCRService] = None,
    ):
        """
        Initialize DocumentProcessor with optional custom extractors for dependency injection.
        """
        self.pdf_extractor = pdf_extractor or PyMuPDFExtractor()
        self._ocr_service = ocr_service

    @property
    def ocr_service(self) -> OCRService:
        """Lazily resolves the OCR service singleton if not explicitly injected."""
        if self._ocr_service is None:
            self._ocr_service = get_ocr_service()
        return self._ocr_service

    def process_document(self, pdf_bytes: bytes) -> DocumentProcessingResult:
        """
        Processes a PDF document in memory:
        1. Attempts native selectable text extraction via PyMuPDF.
        2. If meaningful text is found, returns the result with extraction_method='pymupdf'.
        3. If no selectable text is found (e.g. scanned image PDF), falls back to Tesseract OCR
           and returns the result with extraction_method='tesseract'.

        Args:
            pdf_bytes: Raw binary content of the PDF document.

        Returns:
            DocumentProcessingResult containing extracted_text, page_count, extraction_method,
            has_text, page_texts, and confidence.

        Raises:
            InvalidPDFError: If pdf_bytes is empty, corrupted, encrypted, or invalid.
            DocumentProcessingError: If processing fails unexpectedly.
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise InvalidPDFError("Cannot process empty PDF bytes.")

        # Step 1: Attempt native PyMuPDF text extraction
        try:
            native_result: PDFExtractionResult = self.pdf_extractor.extract_text(pdf_bytes)
        except InvalidPDFError:
            # Re-raise invalid PDF errors directly so corrupt PDFs are not erroneously sent to OCR
            raise
        except Exception as e:
            logger.error("Error during PyMuPDF extraction phase: %s", type(e).__name__)
            raise DocumentProcessingError(f"Native PDF extraction failed: {type(e).__name__}") from e

        # Step 2: Check if selectable text exists
        if native_result.has_text:
            logger.info(
                "Document processed successfully via PyMuPDF (pages=%d).",
                native_result.page_count,
            )
            return DocumentProcessingResult(
                extracted_text=native_result.extracted_text,
                page_count=native_result.page_count,
                extraction_method="pymupdf",
                has_text=True,
                page_texts=native_result.page_texts,
                confidence=None,
            )

        # Step 3: Fall back to Tesseract OCR for scanned / image-based PDFs
        logger.info(
            "No selectable text found via PyMuPDF. Falling back to Tesseract OCR (pages=%d).",
            native_result.page_count,
        )
        try:
            ocr_result: PDFOCRResult = self.ocr_service.extract_from_pdf(pdf_bytes)
        except (InvalidPDFError, OCRError):
            raise
        except Exception as e:
            logger.error("Error during OCR fallback phase: %s", type(e).__name__)
            raise DocumentProcessingError(f"OCR document processing failed: {type(e).__name__}") from e

        logger.info(
            "Document processed via Tesseract OCR (pages=%d, has_text=%s).",
            ocr_result.page_count,
            ocr_result.has_text,
        )
        return DocumentProcessingResult(
            extracted_text=ocr_result.extracted_text,
            page_count=ocr_result.page_count,
            extraction_method="tesseract",
            has_text=ocr_result.has_text,
            page_texts=ocr_result.page_texts,
            confidence=ocr_result.average_confidence,
        )


_default_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """
    Returns a shared singleton instance of DocumentProcessor.
    """
    global _default_processor
    if _default_processor is None:
        _default_processor = DocumentProcessor()
    return _default_processor


def process_document(pdf_bytes: bytes) -> DocumentProcessingResult:
    """
    Convenience function to process a PDF document using the default DocumentProcessor.
    """
    return get_document_processor().process_document(pdf_bytes)
