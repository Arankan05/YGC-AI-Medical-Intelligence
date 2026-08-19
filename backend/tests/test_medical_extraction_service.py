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
    assert len(record.findings) == 1
    assert mock_prov.last_prompt is not None
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


def test_extract_from_text_with_malformed_dates_normalizes_to_none():
    raw_ai_output = {
        "document_type_detected": "lab_report",
        "summary": "Blood chemistry panel showing lab results.",
        "confidence_score": 0.95,
        "events": [
            {
                "event_type": "lab_test",
                "event_date": "200X-07-07",
                "title": "Comprehensive Metabolic Panel",
                "description": "Routine lab work.",
            }
        ],
        "medications": [
            {
                "name": "Lipitor 20mg",
                "start_date": "200X-07-07",
                "end_date": "unknown",
            }
        ],
        "lab_results": [
            {
                "test_name": "Fasting Blood Glucose",
                "value": "105",
                "unit": "mg/dL",
                "reference_range": "70-99 mg/dL",
                "result_date": "200X-07-07",
            },
            {
                "test_name": "Hemoglobin A1c",
                "value": "5.8",
                "unit": "%",
                "reference_range": "< 5.7%",
                "result_date": "unknown",
            },
            {
                "test_name": "Serum Creatinine",
                "value": "1.0",
                "unit": "mg/dL",
                "reference_range": "0.7-1.3 mg/dL",
                "result_date": "",
            },
        ],
        "allergies": [],
        "findings": [],
    }

    mock_prov = MockAIProvider(canned_structured_response=raw_ai_output)
    service = MedicalExtractionService(ai_provider=mock_prov)

    record = service.extract_from_text("Lab panel results text")
    assert isinstance(record, ExtractedMedicalRecord)
    assert len(record.lab_results) == 3
    assert record.lab_results[0].test_name == "Fasting Blood Glucose"
    assert record.lab_results[0].value == "105"
    assert record.lab_results[0].result_date is None
    assert record.lab_results[1].test_name == "Hemoglobin A1c"
    assert record.lab_results[1].result_date is None
    assert record.lab_results[2].test_name == "Serum Creatinine"
    assert record.lab_results[2].result_date is None

    assert record.events[0].event_date is None
    assert record.medications[0].start_date is None
    assert record.medications[0].end_date is None


def test_extraction_consultation_prescription_note_rules():
    """
    Verifies that clinical consultation/prescription notes extract:
    - An appropriate event in events with event_date=None when unstated
    - A valid document_type_detected from allowed categories (never 'unknown')
    - A non-null, non-empty clinical summary
    - Strict anti-hallucination: empty lab_results and allergies when absent in source
    - Preserved medication and finding extractions
    """
    raw_ai_output = {
        "document_type_detected": "consultation_note",
        "summary": "Outpatient consultation for Dengue fever. Prescribed Tab Rantac 150mg and CAP SM FIBRO with advice on monitoring body temperature.",
        "confidence_score": 0.92,
        "events": [
            {
                "event_type": "consultation",
                "title": "Clinical Consultation for Dengue",
                "description": "Outpatient evaluation for full body pain, weakness, and fever.",
                "event_date": None,
            }
        ],
        "medications": [
            {
                "name": "Tab Rantac 150mg",
                "normalized_name": "ranitidine",
                "dosage": "150mg",
                "frequency": "1-1-1",
                "instructions": "After meal",
            },
            {
                "name": "CAP SM FIBRO",
                "normalized_name": "sm fibro",
                "dosage": None,
                "frequency": "1-0-1",
            },
        ],
        "lab_results": [],
        "allergies": [],
        "findings": [
            {
                "finding_type": "diagnosis",
                "title": "Dengue",
                "description": "Confirmed diagnosis of Dengue.",
                "risk_level": "high",
                "confidence": 0.95,
            },
            {
                "finding_type": "vital_sign",
                "title": "High Body Temperature",
                "description": "Observed high body temperature.",
                "risk_level": "medium",
                "confidence": 0.9,
            },
        ],
    }

    mock_prov = MockAIProvider(canned_structured_response=raw_ai_output)
    service = MedicalExtractionService(ai_provider=mock_prov)

    record = service.extract_from_text(
        "Full Body Pain, Weakness Feeling, High Body Temperature. Diagnosis: Dengue. Rx: Tab Rantac 150mg, CAP SM FIBRO."
    )

    # A. Event extraction
    assert len(record.events) == 1
    assert record.events[0].event_type == "consultation"
    assert record.events[0].event_date is None
    assert "Dengue" in record.events[0].title

    # B. Document type is never unknown
    assert record.document_type_detected in {"prescription", "lab_report", "discharge_summary", "consultation_note", "other"}
    assert record.document_type_detected != "unknown"

    # C. Summary is non-null and non-empty
    assert record.summary is not None
    assert isinstance(record.summary, str)
    assert len(record.summary.strip()) > 0

    # D & E. No hallucinated labs or allergies
    assert record.lab_results == []
    assert record.allergies == []

    # F & G. Medications and findings intact
    assert len(record.medications) == 2
    assert record.medications[0].name == "Tab Rantac 150mg"
    assert record.medications[0].normalized_name == "ranitidine"
    assert len(record.findings) == 2
    assert record.findings[0].title == "Dengue"

