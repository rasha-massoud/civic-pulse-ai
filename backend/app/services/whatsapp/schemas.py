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
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Compatibility: stores Meta media IDs as "meta:{id}" until S3 media download exists.
    media_urls: list[str] = Field(default_factory=list)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    ai_analyzed: bool = False
    ai_summary: Optional[str] = None
    ai_severity: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_image_findings: list[dict] = Field(default_factory=list)
    ai_uncertainties: list[str] = Field(default_factory=list)


class WhatsAppReportData(BaseModel):
    """Structured report payload produced after user confirmation."""

    reporter_phone: str
    issue_type: str
    description: str
    location_text: str
    # Compatibility field name kept for reports.py / DB photo_url mapping.
    media_urls: list[str] = Field(default_factory=list)
    language: str
    severity: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # AI analysis fields
    ai_summary: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_image_findings: list[dict] = Field(default_factory=list)
    ai_uncertainties: list[str] = Field(default_factory=list)
    status: str = "pending_review"
    source: str = "whatsapp"
