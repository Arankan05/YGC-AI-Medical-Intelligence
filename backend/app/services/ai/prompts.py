"""Clinical prompt engineering and structured extraction templates for medical documents."""

MEDICAL_EXTRACTION_SYSTEM_INSTRUCTION = """You are an expert Clinical Informatics & Medical Intelligence AI assistant.
Your task is to analyze clinical documents (prescriptions, laboratory reports, discharge summaries, doctor consultation notes, patient histories) and extract all pertinent medical entities into a clean, valid JSON structure.

Follow these strict clinical rules:
1. **Factual Accuracy**: Extract ONLY information explicitly mentioned in or directly inferred from the text. Never hallucinate patient data, dosages, or lab results.
2. **Clinical Dates & Safety**:
   - Complete, identifiable dates MUST be formatted strictly as 'YYYY-MM-DD' (e.g., '2026-08-15').
   - Incomplete, ambiguous, partially obscured, or unreadable dates MUST return null.
   - NEVER guess, invent, or extrapolate missing date components (such as unknown year digits, months, or days).
   - Placeholder dates with wildcards or masks (such as '200X-07-07', '20XX-??-??', 'unknown', '202X') are strictly prohibited; return null instead.
3. **Medications & Prescriptions**:
   - `name`: Full brand or prescribed name as written (e.g., 'Augmentin 625mg', 'Metformin HCl 500mg').
   - `normalized_name`: Lowercase active generic pharmaceutical ingredient without dosage/form (e.g., 'amoxicillin and clavulanate potassium', 'metformin').
   - `dosage`: Specific strength/dose (e.g., '625 mg', '500 mg', '10 ml', '1 tablet').
   - `frequency`: Frequency/timing (e.g., 'twice daily', 'once daily after meals', 'TID', 'PRN').
   - `start_date` / `end_date`: Complete date in 'YYYY-MM-DD' format if explicitly present, otherwise null. Never invent missing date parts.
   - `instructions`: Patient instructions or warning notes (e.g., 'take with full glass of water').
4. **Medical Events**:
   - `event_type`: 'consultation', 'lab_test', 'diagnosis', 'procedure', 'admission', 'discharge', or 'prescription'.
   - `event_date`: Complete date in 'YYYY-MM-DD' format if identifiable, otherwise null. Never guess missing date parts.
   - `title`: Short event title (e.g., 'Cardiology Consultation', 'Routine Blood Test', 'Appendectomy').
   - `description`: Contextual details about the visit or event.
5. **Lab Results**:
   - `test_name`: Name of the test/panel parameter (e.g., 'Fasting Blood Glucose', 'Hemoglobin A1c', 'Serum Creatinine', 'WBC').
   - `value`: Measured numerical or qualitative value (e.g., '142', '6.5', '1.1', 'Negative').
   - `unit`: Unit of measurement if present (e.g., 'mg/dL', '%', 'mg/L', '10^3/uL').
   - `reference_range`: Normal/reference interval if provided (e.g., '70 - 99 mg/dL', '4.0 - 5.6%').
   - `result_date`: Complete date in 'YYYY-MM-DD' format if known and unambiguous, otherwise null. Never output placeholder dates like '200X-07-07'.
6. **Allergies**:
   - `medication_name`: Allergen substance / drug name as stated (e.g., 'Penicillin', 'Sulfa Drugs', 'Ibuprofen').
   - `normalized_medication_name`: Lowercase generic allergen (e.g., 'penicillin', 'sulfonamides', 'ibuprofen').
   - `reaction`: Adverse reaction description (e.g., 'Anaphylaxis', 'Urticaria / Rash', 'Dyspnea').
   - `severity`: 'mild', 'moderate', 'severe', or 'life-threatening'.
7. **Findings**:
   - `finding_type`: 'diagnosis', 'vital_sign', 'symptom', 'risk_factor', or 'clinical_note'.
   - `title`: Concise finding title (e.g., 'Uncontrolled Type 2 Diabetes', 'Elevated Blood Pressure').
   - `description`: Clinical observation context.
   - `risk_level`: 'low', 'medium', 'high', or 'critical'.
   - `confidence`: Confidence score between 0.0 and 1.0 (default 0.9).
   - `recommendation`: Recommended clinical action, lifestyle advice, or referral.
8. **Document Summary & Type**:
   - `document_type_detected`: 'prescription', 'lab_report', 'discharge_summary', 'consultation_note', or 'other'.
   - `summary`: 2-3 sentence clinical summary of the document.
   - `confidence_score`: Overall extraction confidence between 0.0 and 1.0.

Your response MUST BE valid JSON adhering to the exact JSON schema provided. Return pure JSON only, without markdown formatting or introductory commentary.
"""

EXTRACTION_JSON_SCHEMA_DESCRIPTION = {
    "type": "object",
    "properties": {
        "document_type_detected": {"type": "string"},
        "summary": {"type": "string"},
        "confidence_score": {"type": "number"},
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "event_date": {"type": ["string", "null"]},
                    "title": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                },
                "required": ["title", "event_type"],
            },
        },
        "medications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "normalized_name": {"type": ["string", "null"]},
                    "dosage": {"type": ["string", "null"]},
                    "frequency": {"type": ["string", "null"]},
                    "start_date": {"type": ["string", "null"]},
                    "end_date": {"type": ["string", "null"]},
                    "instructions": {"type": ["string", "null"]},
                },
                "required": ["name"],
            },
        },
        "lab_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "test_name": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": ["string", "null"]},
                    "reference_range": {"type": ["string", "null"]},
                    "result_date": {"type": ["string", "null"]},
                },
                "required": ["test_name", "value"],
            },
        },
        "allergies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "medication_name": {"type": "string"},
                    "normalized_medication_name": {"type": ["string", "null"]},
                    "reaction": {"type": ["string", "null"]},
                    "severity": {"type": ["string", "null"]},
                },
                "required": ["medication_name"],
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_type": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "risk_level": {"type": ["string", "null"]},
                    "confidence": {"type": ["number", "null"]},
                    "recommendation": {"type": ["string", "null"]},
                },
                "required": ["title", "description"],
            },
        },
    },
    "required": [
        "document_type_detected",
        "summary",
        "confidence_score",
        "events",
        "medications",
        "lab_results",
        "allergies",
        "findings",
    ],
}


def build_medical_extraction_prompt(clinical_text: str) -> str:
    """
    Constructs the prompt sent to the LLM containing the clinical text to analyze.
    """
    return f"""Please extract all structured clinical entities from the following medical document text into JSON adhering strictly to the required schema:

=== CLINICAL DOCUMENT TEXT START ===
{clinical_text.strip()}
=== CLINICAL DOCUMENT TEXT END ===

Return ONLY valid JSON.
"""
