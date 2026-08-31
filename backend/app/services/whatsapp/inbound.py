"""Normalize Meta WhatsApp Cloud API webhook payloads into inbound messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class InboundWhatsAppMessage:
    """Provider-neutral representation of one inbound WhatsApp message."""

    phone: str
    message_id: str
    message_type: str
    body: str = ""
    media_id: Optional[str] = None
    media_content_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_message(raw: dict[str, Any]) -> Optional[InboundWhatsAppMessage]:
    message_type = str(raw.get("type") or "").strip().lower()
    phone = str(raw.get("from") or "").strip()
    message_id = str(raw.get("id") or "").strip()
    if not phone or not message_id or not message_type:
        return None

    body = ""
    media_id: Optional[str] = None
    media_content_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None

    if message_type == "text":
        text_obj = raw.get("text") or {}
        if isinstance(text_obj, dict):
            body = str(text_obj.get("body") or "").strip()

    elif message_type == "image":
        image_obj = raw.get("image") or {}
        if isinstance(image_obj, dict):
            media_id = str(image_obj.get("id") or "").strip() or None
            media_content_type = str(image_obj.get("mime_type") or "").strip() or None
            body = str(image_obj.get("caption") or "").strip()

    elif message_type == "audio":
        audio_obj = raw.get("audio") or {}
        if isinstance(audio_obj, dict):
            media_id = str(audio_obj.get("id") or "").strip() or None
            media_content_type = str(audio_obj.get("mime_type") or "").strip() or None

    elif message_type == "location":
        location_obj = raw.get("location") or {}
        if isinstance(location_obj, dict):
            latitude = _as_float(location_obj.get("latitude"))
            longitude = _as_float(location_obj.get("longitude"))
            location_name = str(location_obj.get("name") or "").strip() or None
            location_address = str(location_obj.get("address") or "").strip() or None

    else:
        logger.info("Ignoring unsupported WhatsApp message type=%s id=%s", message_type, message_id)
        return None

    return InboundWhatsAppMessage(
        phone=phone,
        message_id=message_id,
        message_type=message_type,
        body=body,
        media_id=media_id,
        media_content_type=media_content_type,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
        location_address=location_address,
    )


def parse_meta_webhook(payload: dict[str, Any]) -> list[InboundWhatsAppMessage]:
    """Extract inbound citizen messages from a Meta Cloud API webhook payload.

    Status-only notifications (delivery/read receipts) yield an empty list.
    Missing optional fields never raise.
    """
    messages: list[InboundWhatsAppMessage] = []
    if not isinstance(payload, dict):
        return messages

    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        return messages

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes") or []
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            raw_messages = value.get("messages") or []
            if not isinstance(raw_messages, list):
                continue
            for raw in raw_messages:
                if not isinstance(raw, dict):
                    continue
                parsed = _parse_message(raw)
                if parsed is not None:
                    messages.append(parsed)

    return messages
