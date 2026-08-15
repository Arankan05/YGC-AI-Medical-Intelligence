import json
import logging
import re
from typing import Any, Dict, Optional

import httpx

from app.services.ai.base_provider import (
    AIAuthenticationError,
    AIRateLimitError,
    AIResponseParseError,
    AIServiceError,
    BaseAIProvider,
)

logger = logging.getLogger(__name__)

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAIProvider(BaseAIProvider):
    """
    Google Gemini AI LLM Provider implementation using Gemini REST API with structured JSON output.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        timeout_seconds: float = 60.0,
        http_client: Optional[httpx.Client] = None,
    ):
        """
        Initialize Gemini provider.

        Args:
            api_key: Google Gemini API key.
            model_name: Model identifier (e.g. 'gemini-2.5-flash', 'gemini-1.5-flash').
            timeout_seconds: Request timeout in seconds.
            http_client: Optional injected httpx.Client for testing and connection reuse.
        """
        self.api_key = api_key or ""
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.timeout_seconds)

    def _clean_json_response(self, text: str) -> str:
        """
        Strips markdown code fences and extraneous leading/trailing characters around JSON.
        """
        cleaned = text.strip()
        # Remove ```json ... ``` or ``` ... ``` wrappers
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
        return cleaned

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        """
        Generates text using Google Gemini API.
        """
        if not self.api_key:
            raise AIAuthenticationError("Google Gemini API key is missing or not configured.")

        url = f"{GEMINI_API_BASE_URL}/{self.model_name}:generateContent?key={self.api_key}"

        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if system_instruction:
            body["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        client = self._get_client()
        try:
            response = client.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
            )
        except httpx.TimeoutException as te:
            logger.error("Gemini API request timed out: %s", str(te))
            raise AIServiceError("Gemini AI service request timed out.") from te
        except httpx.RequestError as re_err:
            logger.error("Gemini API network error: %s", str(re_err))
            raise AIServiceError(f"Network error communicating with Gemini AI: {type(re_err).__name__}") from re_err

        if response.status_code == 401 or response.status_code == 403:
            logger.error("Gemini API authentication failed with status %d", response.status_code)
            raise AIAuthenticationError("Invalid or unauthorized Gemini API key.")
        elif response.status_code == 429:
            logger.warning("Gemini API quota or rate limit exceeded")
            raise AIRateLimitError("Gemini AI rate limit or quota exceeded.")
        elif response.status_code != 200:
            logger.error("Gemini API error (status %d): %s", response.status_code, response.text)
            raise AIServiceError(f"Gemini API returned error status {response.status_code}: {response.text}")

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIServiceError("Gemini API returned no candidates.")
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise AIServiceError("Gemini API returned candidate with no parts.")
            return str(parts[0].get("text", "")).strip()
        except json.JSONDecodeError as jde:
            logger.error("Failed to decode Gemini response JSON: %s", response.text)
            raise AIServiceError("Failed to parse Gemini response payload.") from jde

    def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Generates structured JSON data using Google Gemini API with JSON response format.
        """
        if not self.api_key:
            raise AIAuthenticationError("Google Gemini API key is missing or not configured.")

        url = f"{GEMINI_API_BASE_URL}/{self.model_name}:generateContent?key={self.api_key}"

        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }

        if system_instruction:
            body["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        client = self._get_client()
        try:
            response = client.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
            )
        except httpx.TimeoutException as te:
            logger.error("Gemini API structured request timed out: %s", str(te))
            raise AIServiceError("Gemini AI structured request timed out.") from te
        except httpx.RequestError as re_err:
            logger.error("Gemini API structured network error: %s", str(re_err))
            raise AIServiceError(f"Network error communicating with Gemini AI: {type(re_err).__name__}") from re_err

        if response.status_code == 401 or response.status_code == 403:
            logger.error("Gemini API authentication failed with status %d", response.status_code)
            raise AIAuthenticationError("Invalid or unauthorized Gemini API key.")
        elif response.status_code == 429:
            logger.warning("Gemini API quota or rate limit exceeded")
            raise AIRateLimitError("Gemini AI rate limit or quota exceeded.")
        elif response.status_code != 200:
            logger.error("Gemini API error (status %d): %s", response.status_code, response.text)
            raise AIServiceError(f"Gemini API returned error status {response.status_code}")

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIServiceError("Gemini API returned no candidates.")
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise AIServiceError("Gemini API returned candidate with no parts.")
            raw_text = str(parts[0].get("text", "")).strip()
        except json.JSONDecodeError as jde:
            logger.error("Failed to decode Gemini response JSON: %s", response.text)
            raise AIServiceError("Failed to parse Gemini response payload.") from jde

        # Clean code fences if present and parse inner JSON
        cleaned_text = self._clean_json_response(raw_text)
        try:
            parsed_dict = json.loads(cleaned_text)
            if not isinstance(parsed_dict, dict):
                raise AIResponseParseError(f"Expected JSON object/dict from Gemini, got {type(parsed_dict).__name__}")
            return parsed_dict
        except json.JSONDecodeError as e:
            logger.error("Failed to parse structured JSON from text: %s", raw_text)
            raise AIResponseParseError(f"Model output is not valid JSON: {str(e)}") from e
