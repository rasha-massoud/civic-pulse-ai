"""Tests for early AI extraction from rich voice/text transcripts."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import app.services.whatsapp.router as wa_router
from app.services.ai.multimodal import StructuredCivicReport
from app.services.whatsapp.inbound import InboundWhatsAppMessage
from app.services.whatsapp.schemas import ConversationStep, SupportedLanguage
from app.services.whatsapp.service import WhatsAppConversationService
from app.services.whatsapp.session import InMemorySessionStore, set_session_store


RICH_AR_TRANSCRIPT = "سلام، لقيت في حفرة كتير كبيرة على الطريق البحري ببيروت"


def _pothole_analysis(**overrides) -> StructuredCivicReport:
    data = {
        "category": "pothole",
        "severity": "high",
        "language": "ar-lb",
        "summary": "Large pothole on the Beirut coastal road",
        "description": (
            "Citizen reports a very large pothole on the coastal road in Beirut."
        ),
        "citizen_issue_label": "حفرة كبيرة على الطريق",
        "citizen_summary": "توجد حفرة كبيرة جداً على الطريق البحري في بيروت.",
        "location_text": "الطريق البحري ببيروت",
        "latitude": None,
        "longitude": None,
        "image_findings": [],
        "uncertainties": [],
        "confidence": 0.93,
    }
    data.update(overrides)
    return StructuredCivicReport.model_validate(data)


def test_multimodal_keeps_model_location_when_session_has_none():
    """Voice notes put location inside the transcript — do not wipe AI extraction."""
    from app.services.ai.multimodal import MultimodalReportAnalyzer, MultimodalReportInput

    responses = SimpleNamespace(
        parse=lambda **kwargs: SimpleNamespace(output_parsed=_pothole_analysis())
    )
    analyzer = MultimodalReportAnalyzer(
        client=SimpleNamespace(responses=responses), model="test-model"
    )
    result = analyzer.analyze(
        MultimodalReportInput(citizen_text=RICH_AR_TRANSCRIPT, location=None)
    )
    assert result.location_text == "الطريق البحري ببيروت"
    assert result.latitude is None


def test_greeting_processes_first_voice_transcript_in_same_turn():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)

    reply = service.handle_message(phone="96170001111", body=RICH_AR_TRANSCRIPT)

    session = store.get("96170001111")
    assert session is not None
    assert session.description == RICH_AR_TRANSCRIPT
    assert session.raw_citizen_text == RICH_AR_TRANSCRIPT
    assert session.issue_type == "pothole"
    # Phrase extractor may already fill location from the transcript.
    if session.location_text:
        assert "الطريق البحري" in session.location_text or "بحري" in session.location_text
        assert session.step in {
            ConversationStep.AWAITING_PHOTO,
            ConversationStep.AWAITING_CONFIRMATION,
        }
    else:
        assert session.step == ConversationStep.AWAITING_LOCATION
        assert "وين" in reply or "Where" in reply or "موقع" in reply.lower() or "location" in reply.lower() or "المنطقة" in reply


def test_early_ai_extraction_fills_location_and_skips_reasking(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    analysis_calls = {"n": 0}

    def fake_analyze(**kwargs):
        analysis_calls["n"] += 1
        assert RICH_AR_TRANSCRIPT in (kwargs.get("citizen_text") or "")
        return _pothole_analysis()

    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)

    # Simulate conversation service storing the transcript first.
    service.handle_message(phone="96170002222", body=RICH_AR_TRANSCRIPT)
    session = store.get("96170002222")
    assert session is not None
    assert session.raw_citizen_text == RICH_AR_TRANSCRIPT
    assert session.step in {
        ConversationStep.AWAITING_LOCATION,
        ConversationStep.AWAITING_PHOTO,
        ConversationStep.AWAITING_CONFIRMATION,
    }

    asyncio.run(wa_router._ensure_analysis("96170002222", allow_early=True))

    updated = store.get("96170002222")
    assert updated is not None
    assert updated.ai_analyzed is True
    assert updated.issue_type == "pothole"
    assert updated.location_text == "الطريق البحري ببيروت"
    assert updated.ai_severity == "high"
    assert updated.ai_confidence == 0.93
    assert service.missing_required_fields(updated) == []

    reply = service.reply_for_missing_fields(updated)
    # Location was filled → do not ask for location again.
    assert "وين" not in reply
    assert "Where is the issue" not in reply
    assert "موقع أدق" not in reply
    # Photo is optional; with AI-ready fields the flow may confirm immediately.
    assert updated.location_text == "الطريق البحري ببيروت"
    assert "لس بيلم" not in reply

    # Duplicate call must not re-invoke the model.
    asyncio.run(wa_router._ensure_analysis("96170002222", allow_early=True))
    assert analysis_calls["n"] == 1

    set_session_store(InMemorySessionStore())


def test_process_inbound_voice_uses_early_extraction(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    async def fake_body(message):
        return RICH_AR_TRANSCRIPT, None

    sent: list[str] = []

    async def fake_send(*, to: str, text: str) -> None:
        sent.append(text)

    monkeypatch.setattr(wa_router, "_body_for_conversation", fake_body)
    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(
        wa_router, "analyze_civic_report", lambda **kwargs: _pothole_analysis()
    )
    monkeypatch.setattr(
        wa_router.get_idempotency_store(),
        "mark_completed",
        lambda _mid: None,
    )
    monkeypatch.setattr(
        wa_router.get_idempotency_store(),
        "mark_failed",
        lambda _mid: None,
    )

    message = InboundWhatsAppMessage(
        phone="96170003333",
        message_id="wamid.VOICE.RICH",
        message_type="audio",
        body="",
        media_id="AUD1",
        media_content_type="audio/ogg",
    )
    asyncio.run(wa_router.process_inbound_message(message))

    session = store.get("96170003333")
    assert session is not None
    assert session.location_text == "الطريق البحري ببيروت"
    assert session.issue_type == "pothole"
    assert session.raw_citizen_text == RICH_AR_TRANSCRIPT
    assert sent
    assert "وين" not in sent[0]
    assert "Where is the issue" not in sent[0]
    assert "موقع أدق" not in sent[0]

    set_session_store(InMemorySessionStore())
