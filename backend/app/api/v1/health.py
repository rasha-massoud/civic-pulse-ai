from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.ai.transcription import get_whisper_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """API readiness probe — database must be up; Whisper may still be warming."""
    db.execute(text("SELECT 1"))
    whisper = get_whisper_status()
    return {
        "status": "ok",
        "api_ready": True,
        "database": "connected",
        "whisper_ready": whisper["ready"],
        "whisper": whisper,
    }
