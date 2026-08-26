"""Download WhatsApp media from the Meta Cloud API Graph endpoint."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# WhatsApp voice notes are typically well under this; reject runaway downloads.
MAX_MEDIA_BYTES = 16 * 1024 * 1024


@dataclass
class MediaDownload:
    content: bytes
    mime_type: Optional[str]
    media_id: str


def _auth_headers() -> dict[str, str]:
    token = settings.META_WHATSAPP_ACCESS_TOKEN.strip()
    if not token:
        raise ValueError("META_WHATSAPP_ACCESS_TOKEN is not configured")
    return {"Authorization": f"Bearer {token}"}


def _graph_base() -> str:
    version = settings.META_GRAPH_API_VERSION.strip() or "v23.0"
    return f"https://graph.facebook.com/{version}"


async def get_media_metadata(media_id: str) -> dict:
    """Fetch temporary media URL / MIME metadata for a Meta media ID."""
    media_id = (media_id or "").strip()
    if not media_id:
        raise ValueError("media_id is required")

    url = f"{_graph_base()}/{media_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=_auth_headers())
        if response.is_error:
            logger.error(
                "Meta media metadata failed | status=%s media_id=%s body=%s",
                response.status_code,
                media_id,
                response.text[:300],
            )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not data.get("url"):
            raise ValueError("Meta media metadata missing download URL")
        return data


async def download_media(media_id: str) -> MediaDownload:
    """Download media bytes for a Meta WhatsApp media ID."""
    metadata = await get_media_metadata(media_id)
    download_url = str(metadata["url"])
    mime_type = str(metadata.get("mime_type") or "").strip() or None

    headers = _auth_headers()
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(download_url, headers=headers)
        if response.is_error:
            logger.error(
                "Meta media download failed | status=%s media_id=%s",
                response.status_code,
                media_id,
            )
        response.raise_for_status()

        content = response.content
        if not content:
            raise ValueError("Meta media download returned empty body")
        if len(content) > MAX_MEDIA_BYTES:
            raise ValueError(
                f"Media exceeds size limit ({len(content)} > {MAX_MEDIA_BYTES} bytes)"
            )

        # Prefer Content-Type from the download response when metadata omitted it.
        if not mime_type:
            header_type = (response.headers.get("content-type") or "").split(";")[0].strip()
            mime_type = header_type or None

        logger.info(
            "Meta media downloaded | media_id=%s bytes=%d mime=%s",
            media_id,
            len(content),
            mime_type,
        )
        return MediaDownload(content=content, mime_type=mime_type, media_id=media_id)
