import pytest

from app.schemas.extraction import ExtractedMedicalRecord
from app.services.ai.base_provider import AIResponseParseError, AIServiceError
from app.services.ai.mock_provider import MockAIProvider
from app.services.medical_extraction_service import MedicalExtractionService


def test_extract_from_empty_text():
    mock_prov = MockAIProvider()
    service = MedicalExtractionService(ai_provider=mock_prov)

    res1 = service.extract_from_text("")
    assert res1.confidence_score == 0.0
    assert len(res1.medications) == 0
    assert mock_prov.last_prompt is None  # Should not have called provider

    res2 = service.extract_from_text("   \n\t  ")
    assert res2.confidence_score == 0.0


def test_extract_from_text_success():
    mock_prov = MockAIProvider()
    service = MedicalExtractionService(ai_provider=mock_prov)

    clinical_text = "Patient diagnosed with Acute Sinusitis. Prescribed Amoxicillin 500mg TID for 10 days."
    record = service.extract_from_text(clinical_text)

    assert isinstance(record, ExtractedMedicalRecord)
    assert record.document_type_detected == "prescription"
    assert len(record.medications) == 1
    assert record.medications[0].name == "Amoxicillin 500mg"
    assert len(record.events) == 1
    assert len(record.lab_results) == 1
    assert len(record.allergies) == 1
    assert len(record.findings) == 1
    assert "CLINICAL DOCUMENT TEXT START" in mock_prov.last_prompt


def test_extract_from_text_validation_error():
    # Return invalid data structure (e.g. confidence_score out of range)
    invalid_data = {
        "confidence_score": 99.0,  # Invalid: must be <= 1.0
        "document_type_detected": "prescription",
        "summary": "Invalid score",
        "events": [],
        "medications": [],
        "lab_results": [],
        "allergies": [],
        "findings": [],
    }
    mock_prov = MockAIProvider(canned_structured_response=invalid_data)
    service = MedicalExtractionService(ai_provider=mock_prov)

    with pytest.raises(AIResponseParseError):
        service.extract_from_text("Some text")


def test_extract_from_text_ai_service_error():
    class FailingProvider(MockAIProvider):
        def generate_structured(self, prompt, system_instruction=None, temperature=0.1):
            raise AIServiceError("Network dropped")

    service = MedicalExtractionService(ai_provider=FailingProvider())
    with pytest.raises(AIServiceError) as exc_info:
        service.extract_from_text("Some text")
    assert "Network dropped" in str(exc_info.value)
