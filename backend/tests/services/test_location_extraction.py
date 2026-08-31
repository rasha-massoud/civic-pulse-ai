"""Tests for textual location extraction from Arabic/English transcripts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai.multimodal import (
    MultimodalReportAnalyzer,
    MultimodalReportInput,
    StructuredCivicReport,
    extract_location_text_from_transcript,
)
from app.services.whatsapp.schemas import WhatsAppSession
from app.services.whatsapp.service import WhatsAppConversationService
from app.services.whatsapp.session import InMemorySessionStore


@pytest.mark.parametrize(
    ("transcript", "expected_substring"),
    [
        ("هناك حفرة كبيرة على طريق الحمرا", "طريق الحمرا"),
        ("في حفرة على شارع الحمرا", "شارع الحمرا"),
        ("في مشكلة على الطريق البحري ببيروت", "الطريق البحري ببيروت"),
        ("في زبالة مسكرة الطريق بسوديكو", "سوديكو"),
        ("pothole near AUB main gate", "near AUB main gate"),
    ],
)
def test_extract_location_text_from_transcript(transcript: str, expected_substring: str):
    extracted = extract_location_text_from_transcript(transcript)
    assert extracted is not None
    assert expected_substring in extracted


@pytest.mark.parametrize(
    "transcript",
    [
        "هناك حفرة كبيرة على طريق الحمرا",
        "في حفرة على شارع الحمرا",
        "في مشكلة على الطريق البحري ببيروت",
        "pothole near AUB main gate",
    ],
)
def test_analyzer_fallback_fills_location_when_model_returns_null(transcript: str):
    """Even if OpenAI leaves location_text null, the phrase fallback must fill it."""
    null_location = StructuredCivicReport.model_validate(
        {
            "category": "pothole",
            "severity": "medium",
            "language": "ar-lb",
            "summary": "Pothole reported",
            "description": "Citizen reports a pothole.",
            "location_text": None,
            "latitude": None,
            "longitude": None,
            "image_findings": [],
            "uncertainties": [],
            "confidence": 0.7,
        }
    )
    responses = SimpleNamespace(
        parse=lambda **kwargs: SimpleNamespace(output_parsed=null_location)
    )
    analyzer = MultimodalReportAnalyzer(
        client=SimpleNamespace(responses=responses), model="test-model"
    )

    result = analyzer.analyze(MultimodalReportInput(citizen_text=transcript))

    assert (result.location_text or "").strip()
    assert result.latitude is None
    assert result.longitude is None


@pytest.mark.parametrize(
    "transcript",
    [
        "هناك حفرة كبيرة على طريق الحمرا",
        "في حفرة على شارع الحمرا",
        "في مشكلة على الطريق البحري ببيروت",
        "pothole near AUB main gate",
    ],
)
def test_missing_required_fields_not_location_after_extraction(transcript: str):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170004444",
        description=transcript,
        issue_type="pothole",
        location_text=extract_location_text_from_transcript(transcript),
        ai_analyzed=True,
        ai_severity="medium",
        ai_confidence=0.7,
    )
    store.set(session.phone, session)

    assert "location" not in service.missing_required_fields(session)


def test_missing_required_fields_accepts_coordinates_without_text():
    service = WhatsAppConversationService(store=InMemorySessionStore())
    session = WhatsAppSession(
        phone="96170005555",
        description="pothole",
        issue_type="pothole",
        latitude=33.89,
        longitude=35.48,
    )
    assert "location" not in service.missing_required_fields(session)


def test_apply_multimodal_result_uses_fallback_location_text():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170006666",
        description="هناك حفرة كبيرة على طريق الحمرا",
        issue_type="pothole",
    )
    store.set(session.phone, session)

    result = StructuredCivicReport.model_validate(
        {
            "category": "pothole",
            "severity": "medium",
            "language": "ar-lb",
            "summary": "Large pothole on Hamra road",
            "description": "Citizen reports a large pothole on Hamra road.",
            "location_text": "طريق الحمرا",
            "latitude": None,
            "longitude": None,
            "image_findings": [],
            "uncertainties": [],
            "confidence": 0.7,
        }
    )
    service.apply_multimodal_result(session, result)

    updated = store.get(session.phone)
    assert updated is not None
    assert updated.location_text == "طريق الحمرا"
    assert "location" not in service.missing_required_fields(updated)
