import logging
from typing import Optional

from app.core.config import get_settings
from app.services.ai.base_provider import BaseAIProvider
from app.services.ai.gemini_provider import GeminiAIProvider
from app.services.ai.mock_provider import MockAIProvider

logger = logging.getLogger(__name__)

_global_ai_provider: Optional[BaseAIProvider] = None


def get_ai_provider(provider_name: Optional[str] = None) -> BaseAIProvider:
    """
    Factory function to get or create an AI provider instance.
    Defaults to the AI_PROVIDER specified in application Settings (e.g. 'gemini').
    """
    global _global_ai_provider
    if _global_ai_provider is not None and provider_name is None:
        return _global_ai_provider

    settings = get_settings()
    selected_provider = (provider_name or settings.AI_PROVIDER or "gemini").strip().lower()

    if selected_provider == "gemini":
        return GeminiAIProvider(
            api_key=settings.AI_API_KEY,
            model_name=settings.AI_MODEL or "gemini-3.5-flash-lite",
        )
    elif selected_provider == "mock":
        return MockAIProvider()
    else:
        logger.warning(
            "Unknown AI_PROVIDER '%s' requested, falling back to GeminiAIProvider.",
            selected_provider,
        )
        return GeminiAIProvider(
            api_key=settings.AI_API_KEY,
            model_name=settings.AI_MODEL or "gemini-3.5-flash-lite",
        )


def set_ai_provider(provider: Optional[BaseAIProvider]) -> None:
    """
    Sets a global AI provider instance (useful for injecting mocks during testing).
    """
    global _global_ai_provider
    _global_ai_provider = provider
