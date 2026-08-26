"""Send WhatsApp replies via the Meta Cloud API Graph endpoint."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _messages_url() -> str:
    version = settings.META_GRAPH_API_VERSION.strip() or "v23.0"
    phone_number_id = settings.META_WHATSAPP_PHONE_NUMBER_ID.strip()
    if not phone_number_id:
        raise ValueError("META_WHATSAPP_PHONE_NUMBER_ID is not configured")
    return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"


async def send_text_message(to: str, text: str) -> None:
    """Send a plain-text WhatsApp message to a citizen phone number."""
    token = settings.META_WHATSAPP_ACCESS_TOKEN.strip()
    if not token:
        raise ValueError("META_WHATSAPP_ACCESS_TOKEN is not configured")

    recipient = to.strip()
    body = (text or "").strip()
    if not recipient or not body:
        logger.warning("Skipping outbound WhatsApp message — empty recipient or body")
        return

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": body,
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    logger.info(
        "Sending WhatsApp text | to=%s body_len=%d",
        recipient,
        len(body),
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(_messages_url(), json=payload, headers=headers)
        if response.is_error:
            # Never log the access token; response body may still help debugging.
            logger.error(
                "Meta WhatsApp send failed | status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
        logger.info("Meta WhatsApp reply sent | to=%s body_len=%d", recipient, len(body))
