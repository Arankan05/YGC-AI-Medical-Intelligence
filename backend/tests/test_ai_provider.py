import json
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.services.ai.base_provider import (
    AIAuthenticationError,
    AIRateLimitError,
    AIResponseParseError,
    AIServiceError,
)
from app.services.ai.factory import get_ai_provider, set_ai_provider
from app.services.ai.gemini_provider import GeminiAIProvider
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai.prompts import (
    MEDICAL_EXTRACTION_SYSTEM_INSTRUCTION,
    build_medical_extraction_prompt,
)


def test_build_medical_extraction_prompt():
    prompt = build_medical_extraction_prompt("Rx: Amoxicillin 500mg PO TID")
    assert "CLINICAL DOCUMENT TEXT START" in prompt
    assert "Amoxicillin 500mg PO TID" in prompt
    assert "CLINICAL DOCUMENT TEXT END" in prompt


def test_gemini_missing_api_key():
    provider = GeminiAIProvider(api_key="")
    with pytest.raises(AIAuthenticationError) as exc_info:
        provider.generate_text("Hello")
    assert "missing" in str(exc_info.value).lower()

    with pytest.raises(AIAuthenticationError):
        provider.generate_structured("Hello")


def test_gemini_model_name_normalization():
    p1 = GeminiAIProvider(api_key="key", model_name="models/gemini-3.5-flash-lite")
    assert p1.model_name == "gemini-3.5-flash-lite"

    p2 = GeminiAIProvider(api_key="key", model_name="  gemini-3.5-flash-lite  ")
    assert p2.model_name == "gemini-3.5-flash-lite"


def test_gemini_header_authentication_used():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Hello world"}]}}
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiAIProvider(api_key="my-secret-key-123", model_name="gemini-3.5-flash-lite", http_client=mock_client)
    provider.generate_text("Hi")

    mock_client.post.assert_called_once()
    call_args, call_kwargs = mock_client.post.call_args

    # Verify URL does NOT have key in query string
    assert "key=" not in call_args[0]
    assert call_args[0].endswith("v1beta/models/gemini-3.5-flash-lite:generateContent")

    # Verify header contains key
    headers = call_kwargs.get("headers", {})
    assert headers.get("x-goog-api-key") == "my-secret-key-123"


def test_gemini_generate_text_success():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Patient has mild hypertension."}]
                }
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiAIProvider(api_key="fake-test-key", http_client=mock_client)
    result = provider.generate_text("Summarize condition")

    assert result == "Patient has mild hypertension."
    mock_client.post.assert_called_once()


def test_gemini_generate_structured_success_with_code_fences():
    mock_payload = {
        "document_type_detected": "prescription",
        "summary": "Prescription for Metformin.",
        "confidence_score": 0.95,
        "events": [],
        "medications": [{"name": "Metformin", "dosage": "500mg"}],
        "lab_results": [],
        "allergies": [],
        "findings": [],
    }

    # Wrapped in markdown code fence as LLMs sometimes do
    json_wrapped_text = f"```json\n{json.dumps(mock_payload)}\n```"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json_wrapped_text}]
                }
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiAIProvider(api_key="fake-test-key", http_client=mock_client)
    result = provider.generate_structured("Extract medical data")

    assert isinstance(result, dict)
    assert result["document_type_detected"] == "prescription"
    assert len(result["medications"]) == 1
    assert result["medications"][0]["name"] == "Metformin"


def test_gemini_generate_structured_invalid_json():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "This is plain text, not JSON"}]
                }
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiAIProvider(api_key="fake-test-key", http_client=mock_client)
    with pytest.raises(AIResponseParseError):
        provider.generate_structured("Extract medical data")


def test_gemini_auth_error():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"code": 401, "message": "API key not valid", "status": "UNAUTHENTICATED"}}

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiAIProvider(api_key="bad-key", http_client=mock_client)
    with pytest.raises(AIAuthenticationError):
        provider.generate_structured("Extract medical data")


def test_gemini_rate_limit_error():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.json.return_value = {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiAIProvider(api_key="fake-key", http_client=mock_client)
    with pytest.raises(AIRateLimitError):
        provider.generate_structured("Extract medical data")


def test_gemini_server_error():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Google error"
    mock_response.json.side_effect = ValueError()

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiAIProvider(api_key="fake-key", http_client=mock_client)
    with pytest.raises(AIServiceError):
        provider.generate_structured("Extract medical data")


def test_gemini_404_fallback_success():
    # Primary model returns 404, custom fallback model returns 200
    mock_404 = MagicMock(spec=httpx.Response)
    mock_404.status_code = 404
    mock_404.json.return_value = {
        "error": {"code": 404, "message": "models/primary-model is not found", "status": "NOT_FOUND"}
    }

    mock_200 = MagicMock(spec=httpx.Response)
    mock_200.status_code = 200
    mock_200.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": '{"document_type_detected":"prescription","summary":"ok","confidence_score":0.9,"events":[],"medications":[],"lab_results":[],"allergies":[],"findings":[]}'}]}}
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = [mock_404, mock_200]

    provider = GeminiAIProvider(
        api_key="fake-key",
        model_name="primary-model",
        fallback_models=["gemini-3.5-flash-lite"],
        http_client=mock_client,
    )

    result = provider.generate_structured("Extract text")
    assert result["document_type_detected"] == "prescription"
    assert mock_client.post.call_count == 2


def test_gemini_timeout_error():
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")

    provider = GeminiAIProvider(api_key="fake-key", http_client=mock_client)
    with pytest.raises(AIServiceError) as exc_info:
        provider.generate_structured("Extract medical data")
    assert "timed out" in str(exc_info.value).lower()


def test_mock_ai_provider():
    mock_prov = MockAIProvider()
    structured = mock_prov.generate_structured("test prompt")
    assert structured["document_type_detected"] == "prescription"
    assert len(structured["medications"]) == 1
    assert mock_prov.last_prompt == "test prompt"

    text = mock_prov.generate_text("another prompt")
    assert isinstance(text, str)


def test_factory_get_and_set_provider():
    custom_mock = MockAIProvider(canned_text_response="Custom Response")
    set_ai_provider(custom_mock)
    assert get_ai_provider() is custom_mock

    # Reset
    set_ai_provider(None)
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.AI_PROVIDER = "mock"
        mock_settings.return_value.AI_MODEL = "gemini-3.5-flash-lite"
        mock_settings.return_value.AI_API_KEY = "test"
        prov = get_ai_provider("mock")
        assert isinstance(prov, MockAIProvider)
