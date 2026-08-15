"""AI Provider integration and clinical prompt services."""

from app.services.ai.base_provider import (
    AIAuthenticationError,
    AIRateLimitError,
    AIResponseParseError,
    AIServiceError,
    BaseAIProvider,
)
from app.services.ai.factory import get_ai_provider, set_ai_provider
from app.services.ai.gemini_provider import GeminiAIProvider
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.prompts import (
    EXTRACTION_JSON_SCHEMA_DESCRIPTION,
    MEDICAL_EXTRACTION_SYSTEM_INSTRUCTION,
    build_medical_extraction_prompt,
)

__all__ = [
    "BaseAIProvider",
    "GeminiAIProvider",
    "MockAIProvider",
    "AIServiceError",
    "AIAuthenticationError",
    "AIRateLimitError",
    "AIResponseParseError",
    "get_ai_provider",
    "set_ai_provider",
    "MEDICAL_EXTRACTION_SYSTEM_INSTRUCTION",
    "EXTRACTION_JSON_SCHEMA_DESCRIPTION",
    "build_medical_extraction_prompt",
]
