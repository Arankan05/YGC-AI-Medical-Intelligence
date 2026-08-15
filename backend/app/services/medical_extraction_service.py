import logging
from typing import Optional

from pydantic import ValidationError

from app.schemas.extraction import ExtractedMedicalRecord
from app.services.ai.base_provider import (
    AIResponseParseError,
    AIServiceError,
    BaseAIProvider,
)
from app.services.ai.factory import get_ai_provider
from app.services.ai.prompts import (
    MEDICAL_EXTRACTION_SYSTEM_INSTRUCTION,
    build_medical_extraction_prompt,
)

logger = logging.getLogger(__name__)


class MedicalExtractionService:
    """
    Service for extracting structured clinical data from normalized medical document text.
    Coordinates AI Provider prompting, response sanitization, and Pydantic validation.
    """

    def __init__(self, ai_provider: Optional[BaseAIProvider] = None):
        self._ai_provider = ai_provider

    @property
    def ai_provider(self) -> BaseAIProvider:
        if self._ai_provider is None:
            self._ai_provider = get_ai_provider()
        return self._ai_provider

    def extract_from_text(self, text: Optional[str]) -> ExtractedMedicalRecord:
        """
        Extracts structured medical entities from clinical text.

        Args:
            text: Cleaned extracted text from a medical document.

        Returns:
            ExtractedMedicalRecord containing all structured clinical entities.

        Raises:
            AIServiceError: If AI API fails, times out, or output cannot be validated.
        """
        if not text or not isinstance(text, str) or not text.strip():
            logger.info("Empty clinical text provided for extraction; returning empty record.")
            return ExtractedMedicalRecord(
                document_type_detected="unknown",
                summary="No readable text available in document.",
                confidence_score=0.0,
                events=[],
                medications=[],
                lab_results=[],
                allergies=[],
                findings=[],
            )

        prompt = build_medical_extraction_prompt(text)

        try:
            raw_data = self.ai_provider.generate_structured(
                prompt=prompt,
                system_instruction=MEDICAL_EXTRACTION_SYSTEM_INSTRUCTION,
                temperature=0.1,
            )
        except AIServiceError:
            raise
        except Exception as e:
            logger.error("Unexpected error during AI generation: %s", str(e))
            raise AIServiceError(f"AI extraction generation failed: {type(e).__name__}") from e

        try:
            extracted_record = ExtractedMedicalRecord.model_validate(raw_data)
            logger.info(
                "Successfully extracted medical record: events=%d, medications=%d, lab_results=%d, allergies=%d, findings=%d",
                len(extracted_record.events),
                len(extracted_record.medications),
                len(extracted_record.lab_results),
                len(extracted_record.allergies),
                len(extracted_record.findings),
            )
            return extracted_record
        except ValidationError as ve:
            logger.error("Extracted medical record validation failed: %s", str(ve))
            raise AIResponseParseError(f"AI response failed schema validation: {str(ve)}") from ve


_default_extraction_service: Optional[MedicalExtractionService] = None


def get_medical_extraction_service() -> MedicalExtractionService:
    """
    Returns a shared singleton instance of MedicalExtractionService.
    """
    global _default_extraction_service
    if _default_extraction_service is None:
        _default_extraction_service = MedicalExtractionService()
    return _default_extraction_service
