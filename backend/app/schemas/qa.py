from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatCitationSchema(BaseModel):
    """
    Structured document citation referencing verifiable clinical records.
    """

    document_id: Optional[str] = Field(
        default=None,
        description="ID of source document",
        alias="documentId",
    )
    document_title: str = Field(
        ...,
        description="Title or filename of the cited source document",
        alias="documentTitle",
    )
    page: int = Field(
        default=1,
        description="Page number in the source document where evidence was found",
    )
    quote: str = Field(
        ...,
        description="Exact quote or verbatim excerpt from the document",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class ChatRefusalSchema(BaseModel):
    """
    Structured refusal details when the assistant declines to diagnose or prescribe.
    """

    overline: str = Field(
        default="SAFETY NOTICE",
        description="Category badge overline text",
    )
    headline: str = Field(
        ...,
        description="Prominent warning headline explaining why the action was refused",
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="List of alternative questions the user can ask",
    )
    footnote: str = Field(
        default="This assistant explains recorded medical history and does not diagnose or prescribe.",
        description="Clarifying safety disclaimer footnote",
    )

    model_config = ConfigDict(from_attributes=True)


class ChatCtaSchema(BaseModel):
    """
    Provider referral or doctor hand-off call-to-action button.
    """

    label: str = Field(
        default="Find a healthcare provider nearby",
        description="Button action label",
    )
    note: str = Field(
        default="Consult a healthcare professional for diagnosis or treatment changes",
        description="Context note displayed alongside the button",
    )

    model_config = ConfigDict(from_attributes=True)


class AskQuestionRequest(BaseModel):
    """
    Inbound request schema for patient medical Q&A.
    Tenant isolation guarantee: patient_id and user_id are NOT accepted from the client.
    """

    question: str = Field(
        ...,
        description="Patient clinical or medical record question",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional client conversation identifier",
        alias="conversationId",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")
        cleaned = v.strip()
        if len(cleaned) > 2000:
            raise ValueError("Question exceeds maximum allowed length of 2000 characters.")
        return cleaned

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",  # Strictly rejects any unexpected fields such as patient_id or user_id
    )


class AskQuestionResponse(BaseModel):
    """
    Outbound response schema matching the frontend ChatMessage contract.
    """

    id: str = Field(..., description="Unique answer/message identifier")
    role: str = Field(default="assistant", description="Message role (always 'assistant')")
    paragraphs: List[str] = Field(
        default_factory=list,
        description="List of paragraphs composing the clinical answer",
    )
    citations: List[ChatCitationSchema] = Field(
        default_factory=list,
        description="List of verifiable document citations",
    )
    confidence: Optional[int] = Field(
        default=None,
        description="Confidence percentage (0-100)",
    )
    guidance: Optional[str] = Field(
        default=None,
        description="Clinical guidance note",
    )
    refusal: Optional[ChatRefusalSchema] = Field(
        default=None,
        description="Safety refusal details if diagnosing/prescribing was requested",
    )
    cta: Optional[ChatCtaSchema] = Field(
        default=None,
        description="Provider hand-off CTA if medical evaluation is recommended",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Response creation timestamp",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )
