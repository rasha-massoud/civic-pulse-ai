"""Orchestrate Meta voice-note download + Whisper transcription."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Optional

from app.core.config import settings
from app.services.ai.transcription import TranscriptionResult, transcribe_audio
from app.services.whatsapp.media import download_media

logger = logging.getLogger(__name__)

_MIME_SUFFIX = {
    "audio/ogg": ".ogg",
    "audio/opus": ".ogg",
    "application/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/amr": ".amr",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
}

_whisper_semaphore: Optional[asyncio.Semaphore] = None


def _get_whisper_semaphore() -> asyncio.Semaphore:
    """Lazy per-event-loop semaphore limiting concurrent Whisper jobs."""
    global _whisper_semaphore
    if _whisper_semaphore is None:
        limit = max(1, int(settings.WHISPER_MAX_CONCURRENT or 1))
        _whisper_semaphore = asyncio.Semaphore(limit)
        logger.info("Whisper concurrency limit set | max_concurrent=%d", limit)
    return _whisper_semaphore


def reset_whisper_semaphore() -> None:
    """Reset semaphore (tests)."""
    global _whisper_semaphore
    _whisper_semaphore = None


def _suffix_for_mime(mime_type: Optional[str]) -> str:
    if not mime_type:
        return ".ogg"
    key = mime_type.split(";")[0].strip().lower()
    return _MIME_SUFFIX.get(key, ".ogg")


async def transcribe_whatsapp_audio(
    media_id: str,
    mime_type: Optional[str] = None,
    message_id: Optional[str] = None,
) -> TranscriptionResult:
    """Download a WhatsApp voice note and transcribe it with Whisper.

    Whisper runs in a worker thread so the FastAPI event loop stays responsive.
    A semaphore limits concurrent CPU transcriptions.
    Temporary audio files are always deleted.
    """
    media = await download_media(media_id)
    logger.info(
        "Meta audio downloaded | message_id=%s media_id=%s bytes=%d mime=%s",
        message_id or "-",
        media_id,
        len(media.content),
        media.mime_type or mime_type,
    )

    effective_mime = media.mime_type or mime_type
    suffix = _suffix_for_mime(effective_mime)

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(media.content)
            tmp_path = tmp.name

        logger.info(
            "Whisper transcription queued | message_id=%s media_id=%s suffix=%s",
            message_id or "-",
            media_id,
            suffix,
        )
        semaphore = _get_whisper_semaphore()
        async with semaphore:
            logger.info(
                "Whisper transcription started | message_id=%s media_id=%s",
                message_id or "-",
                media_id,
            )
            # Waits on thread-safe model init if preload is still running.
            return await asyncio.to_thread(transcribe_audio, tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.warning("Failed to delete temp audio file | path=%s", tmp_path)
