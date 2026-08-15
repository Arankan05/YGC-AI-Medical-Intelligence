from typing import Any, Dict, Optional

from app.services.ai.base_provider import BaseAIProvider


class MockAIProvider(BaseAIProvider):
    """
    Mock AI Provider for deterministic unit/integration testing without live API keys or network calls.
    """

    def __init__(
        self,
        canned_structured_response: Optional[Dict[str, Any]] = None,
        canned_text_response: Optional[str] = None,
    ):
        self.canned_structured_response = canned_structured_response or {
            "document_type_detected": "prescription",
            "summary": "Patient prescribed Amoxicillin for acute bacterial sinusitis.",
            "confidence_score": 0.95,
            "events": [
                {
                    "event_type": "consultation",
                    "event_date": "2026-03-10",
                    "title": "General Consultation",
                    "description": "Patient presented with facial pain and nasal congestion.",
                }
            ],
            "medications": [
                {
                    "name": "Amoxicillin 500mg",
                    "normalized_name": "amoxicillin",
                    "dosage": "500mg",
                    "frequency": "three times daily",
                    "start_date": "2026-03-10",
                    "end_date": "2026-03-20",
                    "instructions": "Take after meals for 10 days.",
                }
            ],
            "lab_results": [
                {
                    "test_name": "WBC",
                    "value": "11.2",
                    "unit": "10^3/uL",
                    "reference_range": "4.0 - 10.0",
                    "result_date": "2026-03-10",
                }
            ],
            "allergies": [
                {
                    "medication_name": "Penicillin",
                    "normalized_medication_name": "penicillin",
                    "reaction": "Rash",
                    "severity": "moderate",
                }
            ],
            "findings": [
                {
                    "finding_type": "diagnosis",
                    "title": "Acute Sinusitis",
                    "description": "Acute bacterial infection of sinus cavities.",
                    "risk_level": "medium",
                    "confidence": 0.92,
                    "recommendation": "Complete antibiotic course and monitor symptoms.",
                }
            ],
        }
        self.canned_text_response = canned_text_response or "Mock clinical text analysis response."
        self.last_prompt: Optional[str] = None
        self.last_system_instruction: Optional[str] = None

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        return self.canned_text_response

    def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        return self.canned_structured_response
