"""Language and location text helpers for WhatsApp intake."""

from __future__ import annotations

from typing import Optional

from app.services.whatsapp.classifier import detect_language
from app.services.whatsapp.schemas import SupportedLanguage

__all__ = [
    "SupportedLanguage",
    "detect_language",
    "format_location_text",
]


def format_location_text(
    *,
    name: Optional[str] = None,
    address: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> str:
    """Build a readable location string from a Meta native location message."""
    parts: list[str] = []
    if name:
        parts.append(name.strip())
    if address:
        parts.append(address.strip())
    if latitude is not None and longitude is not None:
        parts.append(f"{latitude}, {longitude}")
    return ", ".join(parts)
