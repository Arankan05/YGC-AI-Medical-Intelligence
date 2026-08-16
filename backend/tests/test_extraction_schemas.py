from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.schemas.extraction import (
    ExtractedAllergy,
    ExtractedFinding,
    ExtractedLabResult,
    ExtractedMedicalEvent,
    ExtractedMedicalRecord,
    ExtractedMedication,
    MedicalExtractionResponse,
)


def test_extracted_medical_event_valid():
    event = ExtractedMedicalEvent(
        event_type="consultation",
        event_date=date(2026, 4, 15),
        title="Cardiology Consultation",
        description="Routine follow up for hypertension.",
    )
    assert event.event_type == "consultation"
    assert event.event_date == date(2026, 4, 15)
    assert event.title == "Cardiology Consultation"


def test_extracted_medical_event_defaults():
    event = ExtractedMedicalEvent(title="General Visit")
    assert event.event_type == "consultation"
    assert event.event_date is None
    assert event.description is None


def test_extracted_medication_auto_normalization():
    med = ExtractedMedication(
        name="Amoxicillin 500mg",
        dosage="500mg",
        frequency="twice daily",
        start_date=date(2026, 3, 1),
    )
    assert med.name == "Amoxicillin 500mg"
    # Auto normalized from raw name if normalized_name is not provided
    assert med.normalized_name == "amoxicillin 500mg"

    med2 = ExtractedMedication(
        name="Augmentin",
        normalized_name="Amoxicillin and Clavulanate",
    )
    assert med2.normalized_name == "amoxicillin and clavulanate"


def test_extracted_lab_result_valid():
    lab = ExtractedLabResult(
        test_name="Fasting Blood Sugar",
        value="110",
        unit="mg/dL",
        reference_range="70-99 mg/dL",
        result_date=date(2026, 2, 20),
    )
    assert lab.test_name == "Fasting Blood Sugar"
    assert lab.value == "110"
    assert lab.unit == "mg/dL"


def test_extracted_allergy_normalization():
    allergy = ExtractedAllergy(
        medication_name="Penicillin G",
        reaction="Anaphylaxis",
        severity="severe",
    )
    assert allergy.medication_name == "Penicillin G"
    assert allergy.normalized_medication_name == "penicillin g"
    assert allergy.severity == "severe"


def test_extracted_finding_valid():
    finding = ExtractedFinding(
        finding_type="diagnosis",
        title="Hypertension Stage 1",
        description="Systolic BP consistently between 130-139 mmHg",
        risk_level="medium",
        confidence=0.95,
        recommendation="Dietary modifications and 3-month follow-up",
    )
    assert finding.finding_type == "diagnosis"
    assert finding.risk_level == "medium"
    assert finding.confidence == 0.95


def test_extracted_medical_record_full():
    record = ExtractedMedicalRecord(
        document_type_detected="prescription",
        summary="Patient prescribed Metformin for diabetes management.",
        confidence_score=0.92,
        events=[
            ExtractedMedicalEvent(title="Endocrine Consultation", event_date=date(2026, 1, 10))
        ],
        medications=[
            ExtractedMedication(name="Metformin 500mg", normalized_name="metformin", dosage="500mg")
        ],
        lab_results=[
            ExtractedLabResult(test_name="HbA1c", value="6.8", unit="%")
        ],
        allergies=[
            ExtractedAllergy(medication_name="Sulfa", reaction="Rash")
        ],
        findings=[
            ExtractedFinding(title="Type 2 Diabetes", description="Elevated HbA1c", risk_level="medium")
        ],
    )
    assert record.document_type_detected == "prescription"
    assert len(record.events) == 1
    assert len(record.medications) == 1
    assert len(record.lab_results) == 1
    assert len(record.allergies) == 1
    assert len(record.findings) == 1
    assert record.confidence_score == 0.92


def test_medical_extraction_response_schema():
    doc_id = uuid4()
    patient_id = uuid4()
    record = ExtractedMedicalRecord(
        document_type_detected="lab_report",
        summary="Complete Blood Count",
        confidence_score=0.98,
    )
    response = MedicalExtractionResponse(
        document_id=doc_id,
        patient_id=patient_id,
        status="COMPLETED",
        extracted_record=record,
        persisted_counts={"events": 0, "lab_results": 5},
    )
    assert response.document_id == doc_id
    assert response.patient_id == patient_id
    assert response.status == "COMPLETED"
    assert response.persisted_counts["lab_results"] == 5


def test_extracted_medical_record_invalid_confidence():
    with pytest.raises(ValidationError):
        ExtractedMedicalRecord(
            confidence_score=1.5,  # Must be <= 1.0
        )


@pytest.mark.parametrize(
    "input_date,expected_date",
    [
        ("2026-08-15", date(2026, 8, 15)),
        ("2026/08/15", date(2026, 8, 15)),
        ("08/15/2026", date(2026, 8, 15)),
        (date(2026, 8, 15), date(2026, 8, 15)),
    ],
)
def test_extracted_lab_result_valid_dates(input_date, expected_date):
    lab = ExtractedLabResult(
        test_name="Hemoglobin A1c",
        value="5.6",
        unit="%",
        reference_range="4.0-5.6%",
        result_date=input_date,
    )
    assert lab.test_name == "Hemoglobin A1c"
    assert lab.value == "5.6"
    assert lab.unit == "%"
    assert lab.reference_range == "4.0-5.6%"
    assert lab.result_date == expected_date


@pytest.mark.parametrize(
    "invalid_or_ambiguous_date",
    [
        None,
        "",
        "   ",
        "\t\n",
        "200X-07-07",
        "20XX-01-01",
        "2024-XX-XX",
        "2024-??-??",
        "202X",
        "unknown",
        "UNKNOWN",
        "null",
        "none",
        "N/A",
        "na",
        "undefined",
        "missing",
        "2024",
        "2024-07",
        "July 2024",
        "invalid_date",
    ],
)
def test_extracted_lab_result_invalid_and_ambiguous_dates_become_none(invalid_or_ambiguous_date):
    lab = ExtractedLabResult(
        test_name="Serum Creatinine",
        value="0.9",
        unit="mg/dL",
        reference_range="0.6-1.2 mg/dL",
        result_date=invalid_or_ambiguous_date,
    )
    assert lab.test_name == "Serum Creatinine"
    assert lab.value == "0.9"
    assert lab.unit == "mg/dL"
    assert lab.reference_range == "0.6-1.2 mg/dL"
    assert lab.result_date is None


def test_extracted_event_and_medication_date_sanitization():
    event = ExtractedMedicalEvent(
        title="Follow-up consultation",
        event_date="200X-07-07",
    )
    assert event.event_date is None

    med = ExtractedMedication(
        name="Metformin 500mg",
        start_date="200X-01-01",
        end_date="unknown",
    )
    assert med.start_date is None
    assert med.end_date is None

