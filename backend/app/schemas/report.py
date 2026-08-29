from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int | None
    phone_number: str
    transcribed_text: str | None
    category: str
    severity: str
    latitude: float
    longitude: float
    photo_url: str | None
    media_urls: list[str] | None
    voice_note_url: str | None
    language: str
    created_at: datetime
