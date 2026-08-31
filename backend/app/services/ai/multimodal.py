"""OpenAI multimodal analysis for complete CivicPulse citizen reports.

This module deliberately knows nothing about Meta or Whisper. Callers pass the
text/transcript, already-downloaded images, location, and conversation context;
the service returns a validated object suitable for the report persistence layer.
"""

from __future__ import annotations

import base64
import re
from enum import Enum
from typing import Any, ClassVar, Iterable, Literal, Sequence
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.services.location_quality import is_meaningful_location


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


class CitizenLanguage(str, Enum):
    """Stable, database-safe language codes produced by the model."""

    ENGLISH = "en"
    ARABIC = "ar"
    LEBANESE_ARABIC = "ar-lb"
    ARABIZI = "arabizi"
    MIXED = "mixed"


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

    MAX_BYTES: ClassVar[int] = 10 * 1024 * 1024
    SUPPORTED_MIME_TYPES: ClassVar[set[str]] = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }

    @model_validator(mode="after")
    def exactly_one_source(self) -> "ReportImage":
        if (self.url is None) == (self.content is None):
            raise ValueError("provide exactly one of url or content")
        if self.url is not None:
            parsed = urlparse(self.url)
            if parsed.scheme not in {"http", "https", "data"}:
                raise ValueError("image URL must use http, https, or data")
            if parsed.scheme == "data" and not self.url.startswith("data:image/"):
                raise ValueError("data URL must contain an image")
        if self.content is not None:
            if not self.content:
                raise ValueError("image content cannot be empty")
            if len(self.content) > self.MAX_BYTES:
                raise ValueError("image content exceeds the 10 MB limit")
            if self.mime_type not in self.SUPPORTED_MIME_TYPES:
                raise ValueError("unsupported image MIME type")
            if not _matches_image_signature(self.content, self.mime_type):
                raise ValueError("image content does not match its MIME type")
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
    language: CitizenLanguage = Field(
        description="Dominant citizen language: en, ar, ar-lb, arabizi, or mixed"
    )
    summary: str = Field(description="Short, clear English dashboard title/summary")
    description: str = Field(
        description="Evidence-grounded English report description for the municipality"
    )
    citizen_issue_label: str = Field(
        default="",
        description=(
            "Short citizen-facing issue title in the citizen's language "
            "(e.g. Arabic: تراكم نفايات على الطريق; English: Garbage piled on the road). "
            "Not a raw Whisper transcript."
        ),
    )
    citizen_summary: str = Field(
        default="",
        description=(
            "Short natural citizen-facing description in the citizen's conversation "
            "language for WhatsApp confirmation. Polish unclear transcripts using all "
            "evidence (text + images + location). Do not invent unsupported facts. "
            "Never paste a raw garbled Whisper transcript."
        ),
    )
    location_text: str | None = Field(
        default=None,
        description=(
            "Meaningful citizen-provided place with identifying detail: street + name, "
            "neighborhood/area, landmark, or relative phrase (طريق الحمرا, شارع الحمرا, "
            "الطريق البحري ببيروت, قرب الجامعة الأميركية, near AUB main gate, سوديكو, "
            "Sodeco). Named neighborhoods alone are valid. "
            "Return null for generic fragments alone such as طريق، طريقة، شارع، road, "
            "street, near. Do NOT invent or substitute a different place spelling. "
            "Do NOT require GPS."
        ),
    )
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="GPS latitude only when the citizen supplied coordinates; else null",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="GPS longitude only when the citizen supplied coordinates; else null",
    )
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
Create one structured report by jointly interpreting ALL supplied evidence: the
citizen's text or Whisper transcript (which may be garbled), uploaded photos,
any separate location payload, and prior conversation. Understand English,
Arabic, Lebanese Arabic, Arabizi, and mixed language. Use exactly one category.

Language codes: use en for English, ar for Modern Standard Arabic, ar-lb for
Lebanese Arabic written in Arabic script, arabizi for Arabic written with Latin
letters/numerals, and mixed when more than one is materially present.

Classification rules:
- Jointly weigh transcript claims and image observations. If the transcript is
  unclear/garbled but photos clearly show an issue (e.g. piled garbage), choose
  the category supported by the image evidence.
- Do not keep an incorrect keyword category when stronger multimodal evidence
  supports a different category.
- Do not override a clear, explicit citizen statement merely because of an image;
  reconcile all evidence and lower confidence when they conflict.

Location rules (critical):
- location_text must be a MEANINGFUL identifying place: street + name, area,
  neighborhood, landmark, or relative phrase (طريق الحمرا, شارع الحمرا,
  الطريق البحري ببيروت, جنب الجامعة الأميركية, قرب صيدلية X, near AUB main gate,
  Hamra Street, سوديكو, Sodeco). Named areas/neighborhoods alone ARE valid.
- Return null when the only cue is a generic fragment: طريق، طريقة، شارع، road,
  street, near, here — these are NOT valid locations.
- Extract location_text from the FULL accumulated transcript/conversation when
  a real place is mentioned across turns (issue in message 1, place in message 2).
- Do NOT invent a more precise address than the citizen gave.
- Do NOT silently "correct" an uncertain Whisper spelling into a different known
  place name. If the place is unclear, leave location_text null.
- latitude/longitude are OPTIONAL. Copy exactly only when the citizen sent
  coordinates or a Maps pin. Never geocode. Null coordinates if none supplied.

Citizen-facing vs municipal text:
- summary + description: clear English for the municipality dashboard.
- citizen_issue_label + citizen_summary: short natural wording in the citizen's
  language for WhatsApp confirmation (Arabic for ar/ar-lb; English for en).
- citizen_summary must NOT be a raw Whisper transcript. If the transcript is
  garbled, rewrite a clear summary from the combined evidence without inventing
  unsupported facts.
- NEVER output filler such as "لا يوجد معلومات كافية" / "not enough information"
  when prior conversation turns already describe an issue — merge all turns.
- Preserve important place names; do not invent urgency, identities, or causes.

Other evidence rules:
- Treat the conversation as ONE report. Later messages enrich earlier ones;
  a location-only follow-up must not erase category/description from earlier text.
- Never invent an object, damage, cause, measurement, date, or identity that is
  not supported by the supplied evidence.
- When evidence conflicts or is insufficient, say so in uncertainties, lower
  confidence, and use category "other" if no listed category is well supported.
- Severity: low (limited/non-urgent), medium (meaningful obstruction or service
  failure), high (immediate safety, flooding, or major public-health risk).
"""


# Deterministic fallback when the model returns null despite an obvious place cue.
_AR_LOCATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # على/في/ب + الطريق/طريق/شارع + name (+ optional ببيروت / بـcity)
    re.compile(
        r"(?:على|في|ب)\s*"
        r"(ال?طريق\s+[\u0600-\u06FFA-Za-z0-9]+(?:\s+ب[\u0600-\u06FFA-Za-z0-9]+)?|"
        r"طريق\s+[\u0600-\u06FFA-Za-z0-9]+|"
        r"شارع\s+[\u0600-\u06FFA-Za-z0-9]+|"
        r"ساحة\s+[\u0600-\u06FFA-Za-z0-9]+|"
        r"حي\s+[\u0600-\u06FFA-Za-z0-9]+)",
        re.UNICODE,
    ),
    # جنب / قرب / عند + landmark phrase
    re.compile(
        r"(?:جنب|قرب|عند)\s+[\u0600-\u06FFA-Za-z0-9][\u0600-\u06FFA-Za-z0-9\s]{1,40}",
        re.UNICODE,
    ),
    # Trailing proclitic neighborhood/place: ... بسوديكو (not a hardcoded list)
    re.compile(
        r"(?:^|[\s،,])ب([\u0600-\u06FF]{3,})\s*$",
        re.UNICODE,
    ),
)

_EN_LOCATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:near|at|on|in|by|beside|outside)\s+"
        r"(?:the\s+)?"
        r"[A-Za-z0-9][A-Za-z0-9\s,'\-]{1,50}"
        r"(?:street|st\.?|road|rd\.?|avenue|ave\.?|boulevard|blvd\.?|gate|square|"
        r"campus|pharmacy|hospital|school|university|aub|hamra)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b[A-Za-z][A-Za-z0-9\s,'\-]{0,30}\b(?:street|st\.?|road|rd\.?)\b",
        re.IGNORECASE,
    ),
)


def extract_location_text_from_transcript(text: str) -> str | None:
    """Best-effort textual location from a citizen transcript (no geocoding).

    Used as a safety net when the multimodal model returns null location_text
    despite an obvious street/landmark phrase in the message.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    for pattern in _AR_LOCATION_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            # Trailing ب + place uses a capturing group for the bare name.
            if match.lastindex:
                phrase = match.group(1).strip()
            else:
                phrase = match.group(0).strip()
                phrase = re.sub(r"^(?:على|في|ب)\s*", "", phrase).strip()
            if phrase and is_meaningful_location(phrase):
                return phrase

    for pattern in _EN_LOCATION_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            phrase = match.group(0).strip(" ,.-")
            if phrase and is_meaningful_location(phrase):
                return phrase

    return None


def _matches_image_signature(content: bytes, mime_type: str) -> bool:
    """Perform a small dependency-free check of supported image formats."""
    signatures = {
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/gif": content.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        ),
    }
    return signatures.get(mime_type, False)


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
        f"Accumulated citizen text / transcripts (all turns):\n"
        f"{report_input.citizen_text!r}\n"
        f"Separate location payload (may be empty — still extract places from "
        f"the accumulated transcripts): {location_lines!r}\n"
        f"Full conversation context: {turns!r}\n"
        f"Attached image count: {len(report_input.images)}\n"
        "Merge every citizen turn into one report. A later location-only message "
        "must keep category/description from earlier turns. "
        "If any turn mentions a street/area/neighborhood/landmark, set "
        "location_text to that phrase even when GPS is null."
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

        # Explicit citizen location text wins over model output. When the citizen
        # only mentioned a place inside their transcript/voice note, keep the
        # model's extracted location_text; if the model returned null, fall back
        # to a deterministic phrase extractor (still no geocoding).
        provided_location = (
            report_input.location.text.strip()
            if report_input.location and report_input.location.text
            else ""
        )
        if provided_location and is_meaningful_location(provided_location):
            result.location_text = provided_location
        elif provided_location and not is_meaningful_location(provided_location):
            # Explicit but generic fragments (e.g. "طريق") do not count.
            result.location_text = None
        elif not is_meaningful_location(result.location_text):
            result.location_text = None
            fallback = extract_location_text_from_transcript(report_input.citizen_text)
            if not fallback:
                for turn in report_input.conversation:
                    if turn.role == "citizen":
                        fallback = extract_location_text_from_transcript(turn.text)
                        if fallback:
                            break
            if is_meaningful_location(fallback):
                result.location_text = fallback

        image_count = len(report_input.images)
        if any(item.image_index > image_count for item in result.image_findings):
            raise ValueError("OpenAI returned a finding for a nonexistent image")
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
