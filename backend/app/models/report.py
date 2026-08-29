from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.issue import Issue


class Report(Base):
    """One complete citizen submission, persisted post-session-assembly.

    Anything still in progress (partial WhatsApp session state) lives in
    Redis, not here — see CLAUDE.md's session-based intake design.
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("issues.id"), nullable=True, index=True
    )
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    transcribed_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    voice_note_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # OpenAI multimodal analysis fields
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_image_findings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ai_uncertainties: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    issue: Mapped[Optional["Issue"]] = relationship("Issue", back_populates="reports")
