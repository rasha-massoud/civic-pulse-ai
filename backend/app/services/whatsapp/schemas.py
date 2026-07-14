"""Pydantic schemas for WhatsApp intake sessions and finalized reports."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ConversationStep(str, Enum):
    """Steps in the multi-turn WhatsApp reporting conversation."""

    GREETING = "greeting"
    AWAITING_ISSUE = "awaiting_issue"
    AWAITING_LOCATION = "awaiting_location"
    AWAITING_PHOTO = "awaiting_photo"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class SupportedLanguage(str, Enum):
    """Languages supported in citizen-facing messages."""

    EN = "en"
    AR = "ar"


class WhatsAppSession(BaseModel):
    """In-progress report state for one WhatsApp user."""

    phone: str
    step: ConversationStep = ConversationStep.GREETING
    language: SupportedLanguage = SupportedLanguage.EN
    issue_type: Optional[str] = None
    description: Optional[str] = None
    location_text: Optional[str] = None
    media_urls: list[str] = Field(default_factory=list)


class WhatsAppReportData(BaseModel):
    """Structured report payload produced after user confirmation."""

    reporter_phone: str
    issue_type: str
    description: str
    location_text: str
    media_urls: list[str] = Field(default_factory=list)
    language: str
    status: str = "pending_review"
    source: str = "whatsapp"


class TwilioWebhookPayload(BaseModel):
    """Normalized Twilio WhatsApp webhook form fields."""

    from_number: str = Field(alias="From")
    body: str = ""
    num_media: int = 0
    media_url: Optional[str] = None
    media_content_type: Optional[str] = None

    model_config = {"populate_by_name": True}
