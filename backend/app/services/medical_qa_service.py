import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.ai_analysis import AIAnalysis
from app.models.allergy import Allergy
from app.models.document import Document
from app.models.finding import Finding
from app.models.lab_result import LabResult
from app.models.medical_event import MedicalEvent
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.question import Question
from app.schemas.qa import (
    AskQuestionResponse,
    ChatCitationSchema,
    ChatCtaSchema,
    ChatRefusalSchema,
)
from app.services.ai.base_provider import (
    AIAuthenticationError,
    AIRateLimitError,
    AIResponseParseError,
    AIServiceError,
    BaseAIProvider,
)
from app.services.ai.factory import get_ai_provider
from app.services.ai.prompts import QA_SYSTEM_INSTRUCTION, build_qa_prompt

logger = logging.getLogger(__name__)


class MedicalQaService:
    """
    Service for answering patient questions strictly grounded in their verified medical records.
    Features:
    - Strictly patient-scoped context retrieval.
    - Zero client-supplied tenant ID acceptance.
    - Grounded RAG prompt assembly with medical safety guardrails.
    - Reusable Gemini AI structured JSON output.
    - Full persistence into Question and AIAnalysis tables.
    """

    def __init__(self, ai_provider: Optional[BaseAIProvider] = None):
        self.ai_provider = ai_provider

    def _get_ai_provider(self) -> BaseAIProvider:
        if self.ai_provider is not None:
            return self.ai_provider
        return get_ai_provider()

    def build_patient_context(self, db: Session, patient_id: Any) -> str:
        """
        Retrieves and formats all medical records owned by the authenticated patient.
        Ensures strict tenant isolation (queries only filter by patient_id).
        """
        sections: List[str] = []

        # 1. Medications & Prescriptions
        meds = (
            db.query(Medication)
            .filter(Medication.patient_id == patient_id)
            .order_by(Medication.created_at.desc())
            .all()
        )
        prescriptions = (
            db.query(Prescription)
            .options(joinedload(Prescription.document), joinedload(Prescription.medication))
            .filter(Prescription.patient_id == patient_id)
            .order_by(Prescription.created_at.desc())
            .all()
        )

        if meds or prescriptions:
            med_lines = ["### MEDICATIONS & PRESCRIPTIONS:"]
            for m in meds:
                med_lines.append(f"- Medication: {m.name} (generic: {m.normalized_name})")
            for p in prescriptions:
                med_name = p.medication.name if p.medication else "Medication"
                doc_info = f" [Source: {p.document.file_name} (ID: {p.document_id})]" if p.document else ""
                dates = f", Period: {p.start_date or 'N/A'} to {p.end_date or 'Present'}"
                instructions = f", Instructions: {p.instructions}" if p.instructions else ""
                med_lines.append(
                    f"- Prescription: {med_name}, Dosage: {p.dosage or 'N/A'}, Frequency: {p.frequency or 'N/A'}{dates}{instructions}{doc_info}"
                )
            sections.append("\n".join(med_lines))

        # 2. Lab Results
        labs = (
            db.query(LabResult)
            .options(joinedload(LabResult.document))
            .filter(LabResult.patient_id == patient_id)
            .order_by(LabResult.result_date.desc().nullslast(), LabResult.created_at.desc())
            .all()
        )
        if labs:
            lab_lines = ["### LABORATORY & BIOMARKER RESULTS:"]
            for l in labs:
                doc_info = f" [Source: {l.document.file_name} (ID: {l.document_id})]" if l.document else ""
                unit_str = f" {l.unit}" if l.unit else ""
                ref_str = f" (Reference: {l.reference_range})" if l.reference_range else ""
                date_str = f" on {l.result_date}" if l.result_date else ""
                lab_lines.append(f"- {l.test_name}: {l.value}{unit_str}{ref_str}{date_str}{doc_info}")
            sections.append("\n".join(lab_lines))

        # 3. Allergies
        allergies = (
            db.query(Allergy)
            .options(joinedload(Allergy.source_document))
            .filter(Allergy.patient_id == patient_id)
            .order_by(Allergy.created_at.desc())
            .all()
        )
        if allergies:
            allergy_lines = ["### RECORDED ALLERGIES & ADVERSE REACTIONS:"]
            for a in allergies:
                doc_info = f" [Source: {a.source_document.file_name} (ID: {a.source_document_id})]" if a.source_document else ""
                rxn = f", Reaction: {a.reaction}" if a.reaction else ""
                sev = f", Severity: {a.severity}" if a.severity else ""
                allergy_lines.append(f"- Allergen: {a.medication_name}{rxn}{sev}{doc_info}")
            sections.append("\n".join(allergy_lines))

        # 4. Clinical Findings
        findings = (
            db.query(Finding)
            .filter(Finding.patient_id == patient_id)
            .order_by(Finding.created_at.desc())
            .all()
        )
        if findings:
            finding_lines = ["### CLINICAL FINDINGS:"]
            for f in findings:
                rec = f" (Recommendation: {f.recommendation})" if f.recommendation else ""
                finding_lines.append(f"- [{f.finding_type.upper()}] {f.title}: {f.description}{rec}")
            sections.append("\n".join(finding_lines))

        # 5. Medical Events / Timeline
        events = (
            db.query(MedicalEvent)
            .options(joinedload(MedicalEvent.document))
            .filter(MedicalEvent.patient_id == patient_id)
            .order_by(MedicalEvent.event_date.desc().nullslast(), MedicalEvent.created_at.desc())
            .all()
        )
        if events:
            event_lines = ["### MEDICAL EVENTS & TIMELINE:"]
            for ev in events:
                doc_info = f" [Source: {ev.document.file_name} (ID: {ev.document_id})]" if ev.document else ""
                date_str = f" on {ev.event_date}" if ev.event_date else ""
                event_lines.append(f"- [{ev.event_type.upper()}]{date_str} {ev.title}: {ev.description or ''}{doc_info}")
            sections.append("\n".join(event_lines))

        # 6. Uploaded Documents & Extracted Text
        documents = (
            db.query(Document)
            .filter(Document.patient_id == patient_id)
            .order_by(Document.uploaded_at.desc())
            .all()
        )
        if documents:
            doc_lines = ["### UPLOADED DOCUMENTS & CLINICAL TEXT:"]
            for d in documents:
                text_snippet = (d.extracted_text or "").strip()
                if len(text_snippet) > 2500:
                    text_snippet = text_snippet[:2500] + "... [truncated]"
                pages = f", {d.page_count} pages" if d.page_count else ""
                doc_lines.append(
                    f"--- Document ID: {d.id} | Filename: {d.file_name} | Type: {d.document_type}{pages} ---\n{text_snippet or '[No extracted text]'}"
                )
            sections.append("\n".join(doc_lines))

        if not sections:
            return "No uploaded clinical documents or medical records found for this patient."

        return "\n\n".join(sections)

    def answer_question(
        self,
        db: Session,
        patient: Patient,
        question: str,
        conversation_id: Optional[str] = None,
    ) -> AskQuestionResponse:
        """
        Executes a patient Q&A cycle:
        1. Gathers patient-scoped context.
        2. Queries the AI provider using the strict clinical RAG prompt.
        3. Parses structured JSON response.
        4. Persists Question and AIAnalysis records.
        5. Returns validated AskQuestionResponse.
        """
        clean_question = question.strip()
        if not clean_question:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty.",
            )

        logger.info(
            "Processing Medical Q&A for patient %s (question_len=%d)",
            patient.id,
            len(clean_question),
        )

        patient_context = self.build_patient_context(db, patient.id)
        prompt = build_qa_prompt(patient_context=patient_context, question=clean_question)

        ai_provider = self._get_ai_provider()

        try:
            raw_response = ai_provider.generate_structured(
                prompt=prompt,
                system_instruction=QA_SYSTEM_INSTRUCTION,
                temperature=0.1,
            )
        except AIAuthenticationError as auth_err:
            logger.error("AI provider authentication error during Q&A: %s", str(auth_err))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is temporarily unavailable due to credential configuration.",
            ) from auth_err
        except AIRateLimitError as rate_err:
            logger.warning("AI provider rate limit exceeded during Q&A: %s", str(rate_err))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service capacity is currently full. Please try again in a few moments.",
            ) from rate_err
        except (AIResponseParseError, AIServiceError) as svc_err:
            logger.error("AI provider failure during Q&A: %s", str(svc_err))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to generate clinical answer from AI provider.",
            ) from svc_err
        except Exception as e:
            logger.error("Unexpected error during Q&A execution: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal error occurred while generating the answer.",
            ) from e

        # Extract structured fields
        paragraphs_raw = raw_response.get("paragraphs", [])
        if isinstance(paragraphs_raw, list):
            paragraphs = [str(p).strip() for p in paragraphs_raw if str(p).strip()]
        elif isinstance(paragraphs_raw, str) and paragraphs_raw.strip():
            paragraphs = [paragraphs_raw.strip()]
        else:
            paragraphs = ["No additional details available from your medical records."]

        citations_raw = raw_response.get("citations", [])
        citations: List[ChatCitationSchema] = []
        if isinstance(citations_raw, list):
            for c in citations_raw:
                if isinstance(c, dict) and c.get("document_title") and c.get("quote"):
                    citations.append(
                        ChatCitationSchema(
                            document_id=c.get("document_id"),
                            document_title=str(c["document_title"]),
                            page=int(c.get("page", 1)) if isinstance(c.get("page"), (int, float)) else 1,
                            quote=str(c["quote"]),
                        )
                    )

        confidence_val = raw_response.get("confidence")
        confidence_pct: Optional[int] = None
        if isinstance(confidence_val, (int, float)):
            confidence_pct = int(confidence_val if confidence_val > 1 else confidence_val * 100)
            confidence_pct = max(0, min(100, confidence_pct))

        guidance_str = raw_response.get("guidance")
        guidance: Optional[str] = str(guidance_str) if guidance_str else "Questions answered strictly from your uploaded medical records."

        refusal_dict = raw_response.get("refusal")
        refusal: Optional[ChatRefusalSchema] = None
        if isinstance(refusal_dict, dict) and refusal_dict.get("headline"):
            refusal = ChatRefusalSchema(
                overline=str(refusal_dict.get("overline", "SAFETY NOTICE")),
                headline=str(refusal_dict.get("headline", "Clinical evaluation required")),
                suggestions=[str(s) for s in refusal_dict.get("suggestions", []) if str(s).strip()],
                footnote=str(refusal_dict.get("footnote", "This assistant explains recorded medical history and does not diagnose or prescribe.")),
            )

        cta_dict = raw_response.get("cta")
        cta: Optional[ChatCtaSchema] = None
        if isinstance(cta_dict, dict) and cta_dict.get("label"):
            cta = ChatCtaSchema(
                label=str(cta_dict.get("label", "Find a healthcare provider nearby")),
                note=str(cta_dict.get("note", "Consult a healthcare professional for clinical evaluation")),
            )

        # Persistence in Question and AIAnalysis
        try:
            q_record = Question(
                patient_id=patient.id,
                question=clean_question,
            )
            db.add(q_record)
            db.flush()

            confidence_fraction = (confidence_pct / 100.0) if confidence_pct is not None else None

            analysis_record = AIAnalysis(
                patient_id=patient.id,
                question_id=q_record.id,
                analysis_type="qa",
                result={
                    "paragraphs": paragraphs,
                    "citations": [c.model_dump(by_alias=True) for c in citations],
                    "confidence": confidence_pct,
                    "guidance": guidance,
                    "refusal": refusal.model_dump() if refusal else None,
                    "cta": cta.model_dump() if cta else None,
                },
                confidence=confidence_fraction,
            )
            db.add(analysis_record)
            db.commit()
            db.refresh(analysis_record)

            response_id = str(analysis_record.id)
            raw_created_at = getattr(analysis_record, "created_at", None)
            created_at_time: Optional[datetime] = raw_created_at if isinstance(raw_created_at, datetime) else None
        except Exception as db_err:
            db.rollback()
            logger.error("Failed to persist Q&A analysis to database: %s", str(db_err))
            response_id = str(uuid.uuid4())
            created_at_time = datetime.now(timezone.utc)

        return AskQuestionResponse(
            id=response_id,
            role="assistant",
            paragraphs=paragraphs,
            citations=citations,
            confidence=confidence_pct,
            guidance=guidance,
            refusal=refusal,
            cta=cta,
            created_at=created_at_time,
        )


_qa_service_instance: Optional[MedicalQaService] = None


def get_medical_qa_service() -> MedicalQaService:
    """
    Factory function for FastAPI dependency injection.
    """
    global _qa_service_instance
    if _qa_service_instance is None:
        _qa_service_instance = MedicalQaService()
    return _qa_service_instance
