import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_application_user
from app.db.database import Base, get_db
from app.main import app as fastapi_app
from app.models.ai_analysis import AIAnalysis
from app.models.document import Document
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.question import Question
from app.models.user import User
from app.services.ai.base_provider import (
    AIAuthenticationError,
    AIRateLimitError,
    AIServiceError,
    BaseAIProvider,
)
from app.services.ai.factory import set_ai_provider
from app.services.medical_qa_service import MedicalQaService, get_medical_qa_service

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

QA_ENDPOINT = "/api/qa/ask"


class MockApiAIProvider(BaseAIProvider):
    def __init__(self, response_payload=None, exception_to_raise=None):
        self.response_payload = response_payload or {
            "paragraphs": [
                "Your medical records indicate a prescription for Metformin 500mg taken twice daily."
            ],
            "citations": [
                {
                    "document_id": "doc-rx-1",
                    "document_title": "Discharge_Summary.pdf",
                    "page": 1,
                    "quote": "Metformin 500mg twice daily with meals",
                }
            ],
            "confidence": 95,
            "guidance": "Questions answered strictly from your uploaded medical records.",
            "refusal": None,
            "cta": None,
        }
        self.exception_to_raise = exception_to_raise
        self.last_prompt = None

    def generate_text(self, prompt: str, system_instruction=None, temperature=0.1) -> str:
        if self.exception_to_raise:
            raise self.exception_to_raise
        return "text"

    def generate_structured(self, prompt: str, system_instruction=None, temperature=0.1):
        self.last_prompt = prompt
        if self.exception_to_raise:
            raise self.exception_to_raise
        return self.response_payload


def _create_patient(session, email: str):
    user_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    user = User(id=user_id, email=email)
    patient = Patient(id=patient_id, user_id=user_id)
    session.add(user)
    session.add(patient)
    session.commit()
    session.refresh(user)
    session.refresh(patient)
    return user, patient


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def patient_a(db_session):
    return _create_patient(db_session, "alice@example.com")


@pytest.fixture
def patient_b(db_session):
    return _create_patient(db_session, "bob@example.com")


@pytest.fixture
def mock_ai():
    provider = MockApiAIProvider()
    set_ai_provider(provider)
    yield provider
    set_ai_provider(None)


@pytest.fixture
def client_a(db_session, patient_a, mock_ai):
    user, _ = patient_a

    def override_get_current_user():
        return user

    def override_get_db():
        yield db_session

    def override_qa_service():
        return MedicalQaService(ai_provider=mock_ai)

    fastapi_app.dependency_overrides[get_current_application_user] = override_get_current_user
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_medical_qa_service] = override_qa_service

    with TestClient(fastapi_app) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()


def test_unauthenticated_request_returns_401(db_session):
    fastapi_app.dependency_overrides.clear()

    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(fastapi_app) as anonymous_client:
        res = anonymous_client.post(QA_ENDPOINT, json={"question": "What are my medications?"})
        assert res.status_code == 401

    fastapi_app.dependency_overrides.clear()


def test_authenticated_user_can_ask_question(client_a, db_session, patient_a, mock_ai):
    user_a, patient_a_obj = patient_a

    # Add medication for patient A
    med = Medication(
        id=uuid.uuid4(),
        patient_id=patient_a_obj.id,
        name="Metformin 500mg",
        normalized_name="metformin",
    )
    db_session.add(med)
    db_session.commit()

    res = client_a.post(QA_ENDPOINT, json={"question": "What dosage of Metformin was prescribed?"})
    assert res.status_code == 200

    data = res.json()
    assert "id" in data
    assert data["role"] == "assistant"
    assert len(data["paragraphs"]) > 0
    assert "Metformin 500mg" in data["paragraphs"][0]
    assert data["confidence"] == 95
    assert len(data["citations"]) == 1
    assert data["citations"][0]["documentTitle"] == "Discharge_Summary.pdf"

    # Verify that the patient context sent to the AI contained Metformin
    assert mock_ai.last_prompt is not None
    assert "Metformin 500mg" in mock_ai.last_prompt


def test_tenant_isolation_user_a_cannot_see_user_b_records(client_a, db_session, patient_a, patient_b, mock_ai):
    _, patient_a_obj = patient_a
    _, patient_b_obj = patient_b

    # Add private record to patient B
    secret_med_b = Medication(
        id=uuid.uuid4(),
        patient_id=patient_b_obj.id,
        name="Confidential-Drug-B",
        normalized_name="drug-b",
    )
    db_session.add(secret_med_b)
    db_session.commit()

    res = client_a.post(QA_ENDPOINT, json={"question": "List all my medications"})
    assert res.status_code == 200

    # Ensure patient B's sensitive drug name was NEVER included in the prompt sent to Gemini
    assert mock_ai.last_prompt is not None
    assert "Confidential-Drug-B" not in mock_ai.last_prompt
    assert "drug-b" not in mock_ai.last_prompt


def test_client_cannot_inject_patient_id(client_a):
    """Schema rejects unexpected client fields like patient_id with HTTP 422."""
    res = client_a.post(
        QA_ENDPOINT,
        json={
            "question": "What medications am I taking?",
            "patient_id": str(uuid.uuid4()),
        },
    )
    assert res.status_code == 422


def test_question_and_analysis_are_persisted(client_a, db_session, patient_a):
    user_a, patient_a_obj = patient_a

    res = client_a.post(QA_ENDPOINT, json={"question": "When was my blood test?"})
    assert res.status_code == 200

    # Verify Question record in database
    q = db_session.query(Question).filter(Question.patient_id == patient_a_obj.id).first()
    assert q is not None
    assert q.question == "When was my blood test?"

    # Verify AIAnalysis record in database
    analysis = (
        db_session.query(AIAnalysis)
        .filter(AIAnalysis.patient_id == patient_a_obj.id)
        .filter(AIAnalysis.analysis_type == "qa")
        .first()
    )
    assert analysis is not None
    assert analysis.question_id == q.id
    assert analysis.confidence == 0.95
    assert "paragraphs" in analysis.result


def test_empty_question_rejected_with_422(client_a):
    res = client_a.post(QA_ENDPOINT, json={"question": "   "})
    assert res.status_code == 422


def test_ai_service_error_returns_503(client_a, mock_ai):
    mock_ai.exception_to_raise = AIServiceError("Gemini API connection error")
    res = client_a.post(QA_ENDPOINT, json={"question": "What is my diagnosis?"})
    assert res.status_code == 503
    data = res.json()
    assert "AI service" in data["detail"] or "Failed to generate" in data["detail"]


def test_ai_rate_limit_error_returns_429(client_a, mock_ai):
    mock_ai.exception_to_raise = AIRateLimitError("Rate limit exceeded")
    res = client_a.post(QA_ENDPOINT, json={"question": "What is my diagnosis?"})
    assert res.status_code == 429
    data = res.json()
    assert "capacity is currently full" in data["detail"]


def test_safety_refusal_response_handling(client_a, mock_ai):
    mock_ai.response_payload = {
        "paragraphs": [
            "I cannot adjust your medication dosages. Please contact your prescribing physician."
        ],
        "citations": [],
        "confidence": 99,
        "guidance": "Dosage adjustments require licensed physician approval.",
        "refusal": {
            "overline": "SAFETY NOTICE",
            "headline": "Dosage adjustments require physician approval",
            "suggestions": [
                "What dose of Metformin is currently recorded?",
                "Who was my prescribing physician?",
            ],
            "footnote": "This assistant explains recorded medical history and does not diagnose or prescribe.",
        },
        "cta": {
            "label": "Find a healthcare provider nearby",
            "note": "Consult a healthcare provider for clinical evaluation",
        },
    }

    res = client_a.post(QA_ENDPOINT, json={"question": "Can I double my dose of Metformin?"})
    assert res.status_code == 200

    data = res.json()
    assert data["refusal"] is not None
    assert data["refusal"]["overline"] == "SAFETY NOTICE"
    assert data["refusal"]["headline"] == "Dosage adjustments require physician approval"
    assert len(data["refusal"]["suggestions"]) == 2
    assert data["cta"] is not None
    assert data["cta"]["label"] == "Find a healthcare provider nearby"
