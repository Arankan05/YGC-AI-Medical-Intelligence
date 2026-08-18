import logging
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.records import get_patient_for_user
from app.core.security import get_current_application_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.qa import AskQuestionRequest, AskQuestionResponse
from app.services.medical_qa_service import (
    MedicalQaService,
    get_medical_qa_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["medical_qa"])


@router.post(
    "/ask",
    response_model=AskQuestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question about uploaded medical records",
    description=(
        "Answers patient clinical questions grounded strictly in their verified uploaded records, "
        "enforcing strict tenant isolation and safety refusals for diagnosis or prescription requests."
    ),
)
def ask_patient_question(
    payload: AskQuestionRequest,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
    qa_service: MedicalQaService = Depends(get_medical_qa_service),
) -> AskQuestionResponse:
    """
    Handles authenticated patient medical Q&A.
    Guarantees:
    - Current patient is derived server-side from authenticated user credentials.
    - No client-provided patient_id is accepted.
    - Context strictly scopes to the authenticated patient's records.
    """
    patient = get_patient_for_user(current_user, db)

    return qa_service.answer_question(
        db=db,
        patient=patient,
        question=payload.question,
        conversation_id=payload.conversation_id,
    )
