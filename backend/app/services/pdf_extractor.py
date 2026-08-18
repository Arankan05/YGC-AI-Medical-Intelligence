import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pymupdf

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Base exception for PDF text extraction failures."""
    pass


class InvalidPDFError(PDFExtractionError):
    """Raised when PDF bytes are empty, malformed, or cannot be parsed."""
    pass


@dataclass(frozen=True)
class PDFExtractionResult:
    """
    Structured result of PDF text extraction.

    Attributes:
        extracted_text: Complete extracted text with clear page boundaries.
        page_count: Total number of pages in the PDF document.
        has_text: True if selectable/extractable text was found, False otherwise.
        page_texts: List of extracted text strings per page.
    """
    extracted_text: str
    page_count: int
    has_text: bool
    page_texts: List[str] = field(default_factory=list)


class PyMuPDFExtractor:
    """
    Service for extracting selectable text from PDF documents in memory using PyMuPDF.
    Independent from web frameworks and database logic for modular pipeline reuse.
    """

    def extract_text(self, pdf_bytes: bytes) -> PDFExtractionResult:
        """
        Extracts selectable text page-by-page from in-memory PDF bytes.

        Args:
            pdf_bytes: Raw binary content of the PDF document.

        Returns:
            PDFExtractionResult with extracted_text, page_count, has_text, and page_texts.

        Raises:
            InvalidPDFError: If pdf_bytes is empty, corrupt, or not a readable PDF.
            PDFExtractionError: If an unexpected error occurs during extraction.
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise InvalidPDFError("Cannot extract text from empty PDF bytes.")

        doc: Optional[pymupdf.Document] = None
        try:
            try:
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            except Exception as e:
                logger.error("Failed to open PDF document from memory: %s", str(e))
                raise InvalidPDFError("Provided bytes do not represent a valid or readable PDF document.") from e

            if doc.is_closed:
                raise InvalidPDFError("PDF document stream could not be initialized.")

            if doc.is_encrypted:
                logger.warning("Encrypted PDF document detected.")
                # Attempt to authenticate with blank/empty password
                if not doc.authenticate(""):
                    raise InvalidPDFError("PDF document is encrypted/password-protected and cannot be opened.")

            page_count = len(doc)
            if page_count == 0:
                return PDFExtractionResult(
                    extracted_text="",
                    page_count=0,
                    has_text=False,
                    page_texts=[],
                )

            page_texts: List[str] = []
            for page_index in range(page_count):
                try:
                    page = doc[page_index]
                    raw_page_text = page.get_text("text") or ""
                    text = raw_page_text.strip() if isinstance(raw_page_text, str) else str(raw_page_text).strip()
                    page_texts.append(text)
                except Exception as page_err:
                    logger.warning("Error extracting text from page %d: %s", page_index + 1, str(page_err))
                    page_texts.append("")

            # Combine page texts while preserving page boundaries clearly
            formatted_pages: List[str] = []
            for i, p_text in enumerate(page_texts, start=1):
                if p_text:
                    formatted_pages.append(f"--- Page {i} ---\n{p_text}")
                else:
                    formatted_pages.append(f"--- Page {i} ---")

            full_extracted_text = "\n\n".join(formatted_pages)

            # Check if any page contains meaningful selectable text
            combined_raw = "".join(page_texts).strip()
            has_text = len(combined_raw) > 0

            return PDFExtractionResult(
                extracted_text=full_extracted_text,
                page_count=page_count,
                has_text=has_text,
                page_texts=page_texts,
            )

        except PDFExtractionError:
            raise
        except Exception as e:
            logger.error("Unexpected error during PDF text extraction: %s", str(e))
            raise PDFExtractionError(f"Unexpected error during PDF text extraction: {type(e).__name__}") from e
        finally:
            if doc is not None and not doc.is_closed:
                try:
                    doc.close()
                except Exception as close_err:
                    logger.warning("Error closing PyMuPDF document: %s", str(close_err))


_default_extractor = PyMuPDFExtractor()


def extract_pdf_text(pdf_bytes: bytes) -> PDFExtractionResult:
    """
    Convenience function to extract text from in-memory PDF bytes.
    """
    return _default_extractor.extract_text(pdf_bytes)
