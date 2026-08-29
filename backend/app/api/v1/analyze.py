"""Multimodal AI analysis endpoint for citizen report intake."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

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


class ImageData(BaseModel):
    """Image for analysis - either URL or base64 data."""

    url: str | None = Field(default=None, description="Public URL to image")
    base64: str | None = Field(default=None, description="Base64 encoded image data")
    mime_type: str = "image/jpeg"


class LocationInput(BaseModel):
    """Location information from citizen."""

    text: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ConversationInput(BaseModel):
    """Single turn in conversation."""

    role: str  # "citizen" or "assistant"
    text: str


class AnalyzeReportRequest(BaseModel):
    """Request to analyze a citizen report using multimodal AI."""

    citizen_text: str = Field(description="Direct text or Whisper transcript from citizen")
    location: LocationInput | None = None
    conversation_history: list[ConversationInput] = Field(default_factory=list)
    images: list[ImageData] = Field(default_factory=list)


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
            if turn.role in {"citizen", "assistant"}
        ]
        
        # Build image list
        images = []
        for img in request.images:
            if img.url:
                images.append(ReportImage(url=img.url))
            elif img.base64:
                import base64
                content = base64.b64decode(img.base64)
                images.append(
                    ReportImage(
                        content=content,
                        mime_type=img.mime_type,
                    )
                )
        
        # Call multimodal analysis
        result: StructuredCivicReport = analyze_civic_report(
            citizen_text=request.citizen_text,
            location=location,
            conversation=conversation,
            images=images,
        )
        
        return AnalyzeReportResponse(
            category=result.category.value,
            severity=result.severity.value,
            language=result.language,
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )
