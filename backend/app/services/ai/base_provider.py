import abc
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Base exception for all AI provider integration failures."""
    pass


class AIAuthenticationError(AIServiceError):
    """Raised when the AI provider rejects API credentials (e.g. invalid or missing API key)."""
    pass


class AIRateLimitError(AIServiceError):
    """Raised when the AI provider rate limits or quotas are exceeded."""
    pass


class AIResponseParseError(AIServiceError):
    """Raised when the AI provider output cannot be parsed as valid JSON or adhere to expected schema."""
    pass


class BaseAIProvider(abc.ABC):
    """
    Abstract interface for AI LLM providers.
    Enables provider-independent AI operations (Gemini, OpenAI, Ollama, Mocks).
    """

    @abc.abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        """
        Generates raw text from the AI model.

        Args:
            prompt: User prompt text.
            system_instruction: Optional system instruction/context.
            temperature: Sampling temperature (default 0.1 for high determinism).

        Returns:
            Raw string response from the model.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Generates structured JSON data conforming to instructions.

        Args:
            prompt: User prompt text containing document content and instructions.
            system_instruction: Optional system instruction.
            temperature: Sampling temperature.

        Returns:
            Parsed Python dictionary representing structured JSON output.
        """
        raise NotImplementedError
