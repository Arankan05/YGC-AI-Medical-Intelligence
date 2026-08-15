import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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
    Features:
    - Official Google Gemini v1beta REST API with x-goog-api-key header authentication.
    - Model name normalization (strips 'models/' prefixes).
    - Uses stable gemini-3.5-flash-lite model for fast, structured medical intelligence extraction.
    - Secret-safe detailed error logging (never logs API keys or leaks credentials in URLs).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.5-flash-lite",
        timeout_seconds: float = 60.0,
        http_client: Optional[httpx.Client] = None,
        fallback_models: Optional[List[str]] = None,
    ):
        """
        Initialize Gemini provider.

        Args:
            api_key: Google Gemini API key.
            model_name: Model identifier (default: 'gemini-3.5-flash-lite').
            timeout_seconds: Request timeout in seconds.
            http_client: Optional injected httpx.Client for testing and connection reuse.
            fallback_models: Optional ordered list of fallback model names if primary model is unavailable.
        """
        self.api_key = (api_key or "").strip()
        self.model_name = self._normalize_model_name(model_name or "gemini-3.5-flash-lite")
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

        if fallback_models is not None:
            self.fallback_models = [self._normalize_model_name(m) for m in fallback_models]
        else:
            self.fallback_models = []

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """
        Cleans and normalizes model name, removing leading 'models/' prefix and whitespace.
        """
        if not model_name:
            return "gemini-3.5-flash-lite"
        cleaned = model_name.strip()
        if cleaned.startswith("models/"):
            cleaned = cleaned[7:].strip()
        return cleaned or "gemini-3.5-flash-lite"

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

    def _parse_gemini_error(self, response: httpx.Response) -> str:
        """
        Extracts structured error details from Gemini API error response without exposing secrets.
        """
        try:
            data = response.json()
            if isinstance(data, dict) and "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    msg = err.get("message", "")
                    status_str = err.get("status", "")
                    code = err.get("code", "")
                    return f"[{code}/{status_str}] {msg}".strip()
                return str(err)
        except Exception:
            pass
        return (response.text or "").strip()[:300]

    def _execute_post(
        self,
        model: str,
        body: Dict[str, Any],
        client: httpx.Client,
    ) -> httpx.Response:
        """
        Executes HTTP POST request using header-based authentication (x-goog-api-key).
        Keeps the API key completely out of the URL query string.
        """
        clean_model = self._normalize_model_name(model)
        url = f"{GEMINI_API_BASE_URL}/{clean_model}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            return client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as te:
            logger.error("Gemini API request timed out for model '%s'", clean_model)
            raise AIServiceError(f"Gemini AI request timed out for model '{clean_model}'.") from te
        except httpx.RequestError as re_err:
            logger.error("Gemini API network error for model '%s': %s", clean_model, type(re_err).__name__)
            raise AIServiceError(f"Network error communicating with Gemini AI ({clean_model}): {type(re_err).__name__}") from re_err

    def _call_with_fallback(
        self,
        body: Dict[str, Any],
    ) -> Tuple[httpx.Response, str]:
        """
        Calls Gemini API with primary model, automatically falling back to secondary models on HTTP 404.
        """
        if not self.api_key:
            raise AIAuthenticationError("Google Gemini API key is missing or not configured.")

        models_to_try = [self.model_name] + self.fallback_models
        client = self._get_client()

        last_response: Optional[httpx.Response] = None
        last_model: str = self.model_name

        for idx, model in enumerate(models_to_try):
            last_model = model
            response = self._execute_post(model=model, body=body, client=client)
            last_response = response

            if response.status_code == 200:
                if idx > 0:
                    logger.info(
                        "Successfully called Gemini API using fallback model '%s' (primary '%s' was unavailable)",
                        model,
                        self.model_name,
                    )
                return response, model

            error_detail = self._parse_gemini_error(response)

            # If 404 Not Found, log warning and try next fallback model if available
            if response.status_code == 404 and idx < len(models_to_try) - 1:
                next_model = models_to_try[idx + 1]
                logger.warning(
                    "Gemini API model '%s' returned 404 Not Found: %s. Attempting fallback model '%s'...",
                    model,
                    error_detail,
                    next_model,
                )
                continue

            # For other errors or last candidate, log and handle
            if response.status_code in (401, 403):
                logger.error("Gemini API authentication failed for model '%s' (HTTP %d): %s", model, response.status_code, error_detail)
                raise AIAuthenticationError(f"Invalid or unauthorized Gemini API key: {error_detail}")
            elif response.status_code == 429:
                logger.warning("Gemini API rate limit or quota exceeded for model '%s' (HTTP 429): %s", model, error_detail)
                raise AIRateLimitError(f"Gemini AI rate limit or quota exceeded ({model}): {error_detail}")
            else:
                logger.error("Gemini API error for model '%s' (HTTP %d): %s", model, response.status_code, error_detail)
                raise AIServiceError(f"Gemini API returned error status {response.status_code} for model '{model}': {error_detail}")

        # If loop completed without return or raise
        err_msg = self._parse_gemini_error(last_response) if last_response else "No response"
        raise AIServiceError(f"Gemini API returned error status {last_response.status_code if last_response else 'unknown'} for model '{last_model}': {err_msg}")

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        """
        Generates text using Google Gemini API.
        """
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

        response, model_used = self._call_with_fallback(body)

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIServiceError(f"Gemini API returned no candidates for model '{model_used}'.")
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise AIServiceError(f"Gemini API returned candidate with no parts for model '{model_used}'.")
            return str(parts[0].get("text", "")).strip()
        except json.JSONDecodeError as jde:
            logger.error("Failed to decode Gemini response JSON: %s", response.text[:300])
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

        response, model_used = self._call_with_fallback(body)

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIServiceError(f"Gemini API returned no candidates for model '{model_used}'.")
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise AIServiceError(f"Gemini API returned candidate with no parts for model '{model_used}'.")
            raw_text = str(parts[0].get("text", "")).strip()
        except json.JSONDecodeError as jde:
            logger.error("Failed to decode Gemini response JSON: %s", response.text[:300])
            raise AIServiceError("Failed to parse Gemini response payload.") from jde

        # Clean code fences if present and parse inner JSON
        cleaned_text = self._clean_json_response(raw_text)
        try:
            parsed_dict = json.loads(cleaned_text)
            if not isinstance(parsed_dict, dict):
                raise AIResponseParseError(f"Expected JSON object/dict from Gemini, got {type(parsed_dict).__name__}")
            return parsed_dict
        except json.JSONDecodeError as e:
            logger.error("Failed to parse structured JSON from model '%s': %s", model_used, raw_text[:300])
            raise AIResponseParseError(f"Model output is not valid JSON: {str(e)}") from e
