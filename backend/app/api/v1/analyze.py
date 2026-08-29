"""Multimodal AI analysis endpoint for citizen report intake."""

import asyncio
import base64
import binascii
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.ai.multimodal import (
    CitizenLocation,
    ConversationTurn,
    IssueCategory,
    ReportImage,
    ReportSeverity,
    StructuredCivicReport,
    analyze_civic_report,
)

router = APIRouter(prefix="/analyze", tags=["ai"])
logger = logging.getLogger(__name__)


class ImageData(BaseModel):
    """Image for analysis - either URL or base64 data."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: str | None = Field(default=None, description="Public URL to image")
    base64_data: str | None = Field(
        default=None,
        alias="base64",
        description="Base64 encoded image data",
    )
    mime_type: str = "image/jpeg"

    @model_validator(mode="after")
    def exactly_one_source(self) -> "ImageData":
        if (self.url is None) == (self.base64_data is None):
            raise ValueError("provide exactly one of url or base64")
        return self


class LocationInput(BaseModel):
    """Location information from citizen."""

    text: str | None = None
    model_config = ConfigDict(extra="forbid")

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ConversationInput(BaseModel):
    """Single turn in conversation."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["citizen", "assistant"]
    text: str


class AnalyzeReportRequest(BaseModel):
    """Request to analyze a citizen report using multimodal AI."""

    model_config = ConfigDict(extra="forbid")

    citizen_text: str = Field(
        default="", description="Direct text or Whisper transcript from citizen"
    )
    location: LocationInput | None = None
    conversation_history: list[ConversationInput] = Field(default_factory=list)
    images: list[ImageData] = Field(default_factory=list, max_length=5)


class AnalyzeReportResponse(BaseModel):
    """Response from multimodal AI analysis."""

    category: str
    severity: str
    language: str
    summary: str
    description: str
    location_text: str | None
    latitude: float | None
    longitude: float | None
    image_findings: list[dict]
    uncertainties: list[str]
    confidence: float


@router.post("/report", response_model=AnalyzeReportResponse)
async def analyze_citizen_report(request: AnalyzeReportRequest):
    """Analyze a citizen report using multimodal AI (text + images + location).
    
    This endpoint accepts citizen input and returns a structured analysis
    including issue classification, severity, and summary suitable for
    saving to the database.
    
    Args:
        citizen_text: Direct text or Whisper transcript from citizen
        location: Location information (text and/or coordinates)
        conversation_history: Prior conversation turns for context
        images: Images uploaded by citizen (URL or base64)
    
    Returns:
        Structured analysis with category, severity, summary, and findings
    """
    try:
        # Build location object
        location = None
        if request.location:
            location = CitizenLocation(
                text=request.location.text,
                latitude=request.location.latitude,
                longitude=request.location.longitude,
            )
        
        # Build conversation history
        conversation = [
            ConversationTurn(role=turn.role, text=turn.text)
            for turn in request.conversation_history
        ]
        
        # Build image list
        images = []
        for img in request.images:
            if img.url:
                images.append(ReportImage(url=img.url))
            elif img.base64_data:
                try:
                    content = base64.b64decode(img.base64_data, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ValueError("image contains invalid base64 data") from exc
                images.append(
                    ReportImage(
                        content=content,
                        mime_type=img.mime_type,
                    )
                )
        
        # Call multimodal analysis
        result: StructuredCivicReport = await asyncio.to_thread(
            analyze_civic_report,
            citizen_text=request.citizen_text,
            location=location,
            conversation=conversation,
            images=images,
        )
        
        return AnalyzeReportResponse(
            category=result.category.value,
            severity=result.severity.value,
            language=result.language.value,
            summary=result.summary,
            description=result.description,
            location_text=result.location_text,
            latitude=result.latitude,
            longitude=result.longitude,
            image_findings=result.image_findings,
            uncertainties=result.uncertainties,
            confidence=result.confidence,
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid analysis input: {str(e)}",
        )
    except Exception:
        logger.exception("Unexpected multimodal analysis failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed. Please try again later.",
        )
