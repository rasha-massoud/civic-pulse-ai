"""OpenAI multimodal analysis for complete CivicPulse citizen reports.

This module deliberately knows nothing about Meta or Whisper. Callers pass the
text/transcript, already-downloaded images, location, and conversation context;
the service returns a validated object suitable for the report persistence layer.
"""

from __future__ import annotations

import base64
from enum import Enum
from typing import Any, Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings


class IssueCategory(str, Enum):
    """Canonical categories already used by the WhatsApp/report mapping."""

    POTHOLE = "pothole"
    GARBAGE = "garbage"
    STREET_LIGHT = "street_light"
    WATER_LEAK = "water_leak"
    ROAD_DAMAGE = "road_damage"
    OTHER = "other"


class ReportSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CitizenLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> "CitizenLocation":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["citizen", "assistant"]
    text: str


class ReportImage(BaseModel):
    """An image represented by a public URL, data URL, or raw downloaded bytes."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    url: str | None = None
    content: bytes | None = None
    mime_type: str = "image/jpeg"

    @model_validator(mode="after")
    def exactly_one_source(self) -> "ReportImage":
        if (self.url is None) == (self.content is None):
            raise ValueError("provide exactly one of url or content")
        if self.content is not None and not self.mime_type.startswith("image/"):
            raise ValueError("mime_type must be an image MIME type")
        return self

    def as_image_url(self) -> str:
        if self.url is not None:
            return self.url
        encoded = base64.b64encode(self.content or b"").decode("ascii")
        return f"data:{self.mime_type};base64,{encoded}"


class MultimodalReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citizen_text: str = ""
    location: CitizenLocation | None = None
    conversation: list[ConversationTurn] = Field(default_factory=list)
    images: list[ReportImage] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def has_report_evidence(self) -> "MultimodalReportInput":
        if not self.citizen_text.strip() and not self.images and not self.conversation:
            raise ValueError("at least text, conversation context, or an image is required")
        return self


class ImageFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_index: int = Field(ge=1)
    observation: str
    supports_report: bool


class StructuredCivicReport(BaseModel):
    """Validated result returned by the multimodal model."""

    model_config = ConfigDict(extra="forbid")

    category: IssueCategory
    severity: ReportSeverity
    language: str = Field(description="Dominant citizen language, e.g. en, ar, Lebanese Arabic, Arabizi, mixed")
    summary: str = Field(description="Short, clear dashboard title/summary")
    description: str = Field(description="Evidence-grounded report description")
    location_text: str | None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    image_findings: list[ImageFinding]
    uncertainties: list[str]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> "StructuredCivicReport":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be returned together")
        return self

    def to_whatsapp_report_data(
        self,
        *,
        reporter_phone: str,
        media_urls: Sequence[str] = (),
    ) -> Any:
        """Adapt the analysis to the existing persistence-layer intake schema."""
        # Local import prevents the provider-neutral AI module from being tied to
        # WhatsApp at import time and avoids a future schema import cycle.
        from app.services.whatsapp.schemas import WhatsAppReportData

        return WhatsAppReportData(
            reporter_phone=reporter_phone,
            issue_type=self.category.value,
            description=self.description,
            location_text=self.location_text or "",
            media_urls=list(media_urls),
            language=self.language,
            severity=self.severity.value,
            latitude=self.latitude,
            longitude=self.longitude,
        )


SYSTEM_PROMPT = """You are CivicPulse AI, a municipal report analyst for Beirut.
Create one structured report by jointly interpreting all supplied evidence: the
citizen's text or Whisper transcript, uploaded photos, exact location, and prior
conversation. Understand English, Arabic, Lebanese Arabic, Arabizi, and mixed
language. Use exactly one provided category.

Evidence rules:
- Never invent an object, damage, cause, address, coordinate, measurement, date,
  identity, or urgency that is not supported by the supplied evidence.
- Treat citizen statements as claims and images as observations. Reconcile them;
  do not analyze either source in isolation.
- Copy supplied coordinates exactly. Never infer coordinates from an image or
  place name. If none were supplied, return null coordinates.
- When evidence conflicts or is insufficient, say so in uncertainties, lower
  confidence, and use category "other" if no listed category is well supported.
- Severity means apparent municipal impact: low (limited/non-urgent), medium
  (meaningful obstruction or service failure), high (visible immediate safety,
  flooding, or major public-health risk). Do not exaggerate severity.
- Write summary and description in clear English for the municipality while
  preserving important place names exactly as the citizen supplied them.
"""


def _format_text(report_input: MultimodalReportInput) -> str:
    location = report_input.location
    location_lines = {
        "text": location.text if location else None,
        "latitude": location.latitude if location else None,
        "longitude": location.longitude if location else None,
    }
    turns = [turn.model_dump() for turn in report_input.conversation]
    return (
        "Analyze this citizen report as a single body of evidence.\n"
        f"Citizen text / transcript: {report_input.citizen_text!r}\n"
        f"Citizen-provided location: {location_lines!r}\n"
        f"Conversation context: {turns!r}\n"
        f"Attached image count: {len(report_input.images)}"
    )


def _content(report_input: MultimodalReportInput) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [
        {"type": "input_text", "text": _format_text(report_input)}
    ]
    content.extend(
        {"type": "input_image", "image_url": image.as_image_url(), "detail": "high"}
        for image in report_input.images
    )
    return content


class MultimodalReportAnalyzer:
    """Thin injectable wrapper around OpenAI Responses structured output."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        if client is None:
            if not settings.OPENAI_API_KEY.strip():
                raise ValueError("OPENAI_API_KEY is not configured")
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_MULTIMODAL_TIMEOUT_SECONDS,
            )
        self.client = client
        self.model = (model or settings.OPENAI_MULTIMODAL_MODEL).strip()
        if not self.model:
            raise ValueError("OPENAI_MULTIMODAL_MODEL is not configured")

    def analyze(self, report_input: MultimodalReportInput) -> StructuredCivicReport:
        response = self.client.responses.parse(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": _content(report_input)}],
            text_format=StructuredCivicReport,
            store=False,
        )
        result = response.output_parsed
        if result is None:
            raise ValueError("OpenAI returned no structured civic report")
        if not isinstance(result, StructuredCivicReport):
            result = StructuredCivicReport.model_validate(result)

        # Coordinates are trusted application data, not a model decision. Enforce
        # exact preservation even if a model response attempts to alter them.
        if report_input.location and report_input.location.latitude is not None:
            result.latitude = report_input.location.latitude
            result.longitude = report_input.location.longitude
        else:
            result.latitude = None
            result.longitude = None
        return result


def analyze_civic_report(
    *,
    citizen_text: str = "",
    location: CitizenLocation | None = None,
    conversation: Sequence[ConversationTurn] = (),
    images: Iterable[ReportImage] = (),
    client: Any | None = None,
    model: str | None = None,
) -> StructuredCivicReport:
    """Convenience entry point for WhatsApp or future HTTP intake adapters."""
    report_input = MultimodalReportInput(
        citizen_text=citizen_text,
        location=location,
        conversation=list(conversation),
        images=list(images),
    )
    return MultimodalReportAnalyzer(client=client, model=model).analyze(report_input)
