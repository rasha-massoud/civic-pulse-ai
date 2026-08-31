"""Minimal WhatsApp confirmation + cancel/reset regression tests."""

from __future__ import annotations

import asyncio

import app.services.whatsapp.router as wa_router
from app.services.whatsapp.classifier import format_issue_type
from app.services.whatsapp.inbound import InboundWhatsAppMessage
from app.services.whatsapp.schemas import ConversationStep, SupportedLanguage, WhatsAppSession
from app.services.whatsapp.service import WhatsAppConversationService
from app.services.whatsapp.session import InMemorySessionStore, set_session_store


def _ready_session(**overrides) -> WhatsAppSession:
    data = {
        "phone": "96170004001",
        "language": SupportedLanguage.AR,
        "step": ConversationStep.AWAITING_CONFIRMATION,
        "issue_type": "garbage",
        "description": "Garbage is blocking the street in Hamra.",
        "raw_citizen_text": "في زبالة مسكرة الطريق بالحمرة",
        "citizen_issue_label": "زبالة مسكرت طريق بالحمرة",
        "citizen_summary": "هناك زبالة مسكرت طريق بالحمرة",
        "location_text": "الحمرا",
        "media_urls": ["/uploads/reports/g.jpg"],
        "photo_resolved": True,
        "ai_analyzed": True,
        "ai_summary": "Garbage in Hamra",
        "ai_severity": "medium",
        "ai_confidence": 0.91,
        "ai_uncertainties": ["exact pile size unknown"],
    }
    data.update(overrides)
    return WhatsAppSession(**data)


def test_build_summary_is_minimal_arabic_category_not_sentence():
    """Confirmation is built by WhatsAppConversationService._build_summary."""
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session()

    text = service._build_summary(session)

    assert text.startswith("ملخص البلاغ")
    assert "المشكلة: تراكم نفايات" in text
    assert "الموقع: الحمرا" in text
    assert "الصورة: مرفقة" in text
    assert "الوصف" not in text
    assert "هناك زبالة" not in text
    assert "زبالة مسكرت" not in text
    assert "0.91" not in text
    assert "medium" not in text
    assert session.citizen_summary == "هناك زبالة مسكرت طريق بالحمرة"  # kept internally


def test_build_summary_english_minimal():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session(
        language=SupportedLanguage.EN,
        location_text="Hamra",
        citizen_summary="There is garbage blocking the road in Hamra.",
    )
    text = service._build_summary(session)
    assert text.startswith("Report Summary")
    assert "Issue: Garbage accumulation" in text
    assert "Location: Hamra" in text
    assert "Photo: Attached" in text
    assert "Description" not in text
    assert "blocking the road" not in text


def test_build_summary_omits_photo_when_absent():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session(media_urls=[])
    text = service._build_summary(session)
    assert "صورة" not in text
    assert "Photo" not in text


def test_build_summary_includes_material_extra_only():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session(
        citizen_summary="الطريق مغلق بالكامل بسبب النفايات.",
    )
    text = service._build_summary(session)
    assert "ملاحظة: الطريق مغلق بالكامل بسبب النفايات." in text
    assert "المشكلة: تراكم نفايات" in text


def test_canonical_issue_labels():
    assert format_issue_type("garbage", SupportedLanguage.AR) == "تراكم نفايات"
    assert format_issue_type("pothole", SupportedLanguage.AR) == "حفرة في الطريق"
    assert format_issue_type("water_leak", SupportedLanguage.AR) == "تسرب مياه"
    assert format_issue_type("street_light", SupportedLanguage.AR) == "عطل في إنارة الشارع"
    assert format_issue_type("road_damage", SupportedLanguage.AR) == "ضرر في الطريق"
    assert format_issue_type("garbage", SupportedLanguage.EN) == "Garbage accumulation"


def test_cancel_no_resets_session_english():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session(phone="96170004010", language=SupportedLanguage.EN)
    store.set(session.phone, session)

    reply = service.handle_message(session.phone, "No")
    assert "cancelled" in reply.lower()
    assert "ملخص" not in reply
    assert "Report Summary" not in reply
    assert store.get(session.phone) is None

    # Fresh report must not carry old data.
    service.handle_message(session.phone, "hi")
    fresh = store.get(session.phone)
    assert fresh is not None
    assert fresh.issue_type is None
    assert fresh.location_text is None
    assert fresh.media_urls == []
    assert fresh.raw_citizen_text is None
    assert fresh.citizen_summary is None
    assert fresh.ai_analyzed is False


def test_cancel_la_resets_session_arabic():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session(phone="96170004011")
    store.set(session.phone, session)

    reply = service.handle_message(session.phone, "لا")
    assert "تم إلغاء البلاغ" in reply
    assert "ملخص البلاغ" not in reply
    assert store.get(session.phone) is None


def test_router_no_does_not_regenerate_confirmation(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    session = _ready_session(phone="96170004012")
    store.set(session.phone, session)

    sent: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    def fake_analyze(**kwargs):
        raise AssertionError("AI must not run on confirmation cancel")

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)
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

    msg = InboundWhatsAppMessage(
        message_id="wamid.CANCEL1",
        phone="96170004012",
        message_type="text",
        body="no",
    )
    asyncio.run(wa_router.process_inbound_message(msg))

    assert len(sent) == 1
    assert "cancelled" in sent[0].lower() or "إلغاء" in sent[0]
    assert "ملخص البلاغ" not in sent[0]
    assert "Report Summary" not in sent[0]
    assert store.get("96170004012") is None

    set_session_store(InMemorySessionStore())


def test_router_arabic_la_does_not_regenerate_confirmation(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    session = _ready_session(phone="96170004013")
    store.set(session.phone, session)

    sent: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
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

    msg = InboundWhatsAppMessage(
        message_id="wamid.CANCEL2",
        phone="96170004013",
        message_type="text",
        body="لا",
    )
    asyncio.run(wa_router.process_inbound_message(msg))

    assert len(sent) == 1
    assert "تم إلغاء البلاغ" in sent[0]
    assert "ملخص البلاغ" not in sent[0]
    assert store.get("96170004013") is None

    set_session_store(InMemorySessionStore())
