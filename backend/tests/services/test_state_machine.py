"""Regression coverage for the single-authority WhatsApp state machine."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import app.services.whatsapp.router as wa_router
import app.services.whatsapp.service as wa_service
from app.services.ai.multimodal import StructuredCivicReport
from app.services.whatsapp.inbound import InboundWhatsAppMessage
from app.services.whatsapp.media import MediaDownload
from app.services.whatsapp.schemas import (
    ConversationStep,
    SupportedLanguage,
    WhatsAppSession,
)
from app.services.whatsapp.service import (
    WhatsAppConversationService,
    is_control_utterance,
)
from app.services.whatsapp.session import InMemorySessionStore, set_session_store


def _analysis(
    *,
    category: str = "pothole",
    location: str = "طريق الحمرا",
    with_image: bool = False,
) -> StructuredCivicReport:
    return StructuredCivicReport.model_validate(
        {
            "category": category,
            "severity": "medium",
            "language": "ar-lb",
            "summary": f"{category} reported at {location}",
            "description": f"A citizen reported {category} at {location}.",
            "citizen_issue_label": "حفرة في الطريق",
            "citizen_summary": "توجد مشكلة في الطريق في الموقع المذكور.",
            "location_text": location,
            "latitude": None,
            "longitude": None,
            "image_findings": (
                [
                    {
                        "image_index": 1,
                        "observation": "The image supports the reported issue.",
                        "supports_report": True,
                    }
                ]
                if with_image
                else []
            ),
            "uncertainties": [],
            "confidence": 0.9,
        }
    )


def _ready_session(
    phone: str,
    *,
    language: SupportedLanguage = SupportedLanguage.AR,
) -> WhatsAppSession:
    return WhatsAppSession(
        phone=phone,
        language=language,
        step=ConversationStep.AWAITING_CONFIRMATION,
        issue_type="pothole",
        description="A pothole was reported on Hamra Street.",
        raw_citizen_text="في حفرة على طريق الحمرا",
        location_text="طريق الحمرا",
        photo_resolved=True,
        ai_analyzed=True,
    )


def test_a_voice_photo_confirmation_submits_once_without_yes_as_location(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    sent: list[str] = []
    created: list[object] = []

    async def fake_send(*, to: str, text: str) -> None:
        sent.append(text)

    async def fake_body(message: InboundWhatsAppMessage):
        if message.message_type == "audio":
            return "في حفرة كبيرة على طريق الحمرا", None
        return message.body, None

    async def fake_download(media_id: str) -> MediaDownload:
        return MediaDownload(
            content=b"\xff\xd8\xffimage",
            mime_type="image/jpeg",
            media_id=media_id,
        )

    def fake_analyze(**kwargs):
        return _analysis(with_image=bool(kwargs["images"]))

    def fake_create(data):
        created.append(data)
        return "CIV-000777"

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(wa_router, "_body_for_conversation", fake_body)
    monkeypatch.setattr(wa_router, "download_media", fake_download)
    monkeypatch.setattr(
        wa_router,
        "store_report_image",
        lambda content, mime_type: SimpleNamespace(
            public_url="/uploads/reports/state-machine.jpg",
            path="state-machine.jpg",
        ),
    )
    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)
    monkeypatch.setattr(wa_service, "create_report_from_whatsapp", fake_create)
    monkeypatch.setattr(
        wa_router.get_idempotency_store(), "mark_completed", lambda _mid: None
    )
    monkeypatch.setattr(
        wa_router.get_idempotency_store(), "mark_failed", lambda _mid: None
    )

    messages = [
        InboundWhatsAppMessage(
            message_id="state-A-hi",
            phone="96170010001",
            message_type="text",
            body="Hi",
        ),
        InboundWhatsAppMessage(
            message_id="state-A-voice",
            phone="96170010001",
            message_type="audio",
            body="",
            media_id="voice-1",
            media_content_type="audio/ogg",
        ),
        InboundWhatsAppMessage(
            message_id="state-A-photo",
            phone="96170010001",
            message_type="image",
            body="",
            media_id="image-1",
            media_content_type="image/jpeg",
        ),
    ]
    for message in messages:
        asyncio.run(wa_router.process_inbound_message(message))

    before_yes = store.get("96170010001")
    assert before_yes is not None
    assert before_yes.step == ConversationStep.AWAITING_CONFIRMATION
    assert before_yes.location_text == "طريق الحمرا"
    assert "ارفاق صورة" in sent[1].replace("إ", "ا")
    assert "ملخص البلاغ" in sent[2]

    asyncio.run(
        wa_router.process_inbound_message(
            InboundWhatsAppMessage(
                message_id="state-A-yes",
                phone="96170010001",
                message_type="text",
                body="Yes",
            )
        )
    )

    assert len(created) == 1
    assert created[0].location_text == "طريق الحمرا"
    assert created[0].location_text != "Yes"
    assert "تم إرسال البلاغ بنجاح" in sent[-1]
    assert store.get("96170010001") is None


def test_b_skip_photo_then_arabic_confirmation_submits(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session("96170010002")
    session.step = ConversationStep.AWAITING_PHOTO
    session.photo_resolved = False
    store.set(session.phone, session)
    monkeypatch.setattr(
        wa_service, "create_report_from_whatsapp", lambda data: "CIV-000002"
    )

    confirmation = service.handle_message(session.phone, "تخطي")
    assert session.photo_resolved is True
    assert session.step == ConversationStep.AWAITING_CONFIRMATION
    assert "ملخص البلاغ" in confirmation

    submitted = service.handle_message(session.phone, "نعم")
    assert "تم إرسال البلاغ بنجاح" in submitted
    assert store.get(session.phone) is None


def test_c_no_cancels_without_submission(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session("96170010003", language=SupportedLanguage.EN)
    store.set(session.phone, session)
    monkeypatch.setattr(
        wa_service,
        "create_report_from_whatsapp",
        lambda data: (_ for _ in ()).throw(AssertionError("must not submit")),
    )

    reply = service.handle_message(session.phone, "No")
    assert "cancelled" in reply.lower()
    assert store.get(session.phone) is None


def test_d_multiturn_garbage_sodeco_photo_confirms_accumulated_report():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    phone = "96170010004"

    service.handle_message(phone, "في زبالة كتير")
    location_reply = service.handle_message(phone, "بسوديكو")
    session = store.get(phone)
    assert session is not None
    assert session.step == ConversationStep.AWAITING_PHOTO
    assert "صورة" in location_reply

    service.handle_message(
        phone,
        "",
        media_id="garbage-photo",
        media_content_type="image/jpeg",
    )
    service.apply_multimodal_result(
        session,
        _analysis(category="garbage", location="بسوديكو", with_image=True),
    )
    confirmation = service.decide_next_reply(session)

    assert "في زبالة كتير" in (session.raw_citizen_text or "")
    assert "بسوديكو" in (session.raw_citizen_text or "")
    assert "المشكلة: تراكم نفايات" in confirmation
    assert "الموقع: سوديكو" in confirmation


def test_e_controls_never_become_location_or_evidence_at_wrong_steps():
    assert all(is_control_utterance(word) for word in ("yes", "No", "skip", "نعم"))

    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170010005",
        language=SupportedLanguage.AR,
        step=ConversationStep.AWAITING_LOCATION,
        issue_type="garbage",
        description="Garbage reported",
        raw_citizen_text="في زبالة",
    )
    store.set(session.phone, session)
    original_evidence = session.raw_citizen_text

    for control in ("yes", "No", "skip"):
        service.handle_message(session.phone, control)
        assert session.location_text is None
        assert session.raw_citizen_text == original_evidence
        assert session.photo_resolved is False

    session.location_text = "سوديكو"
    session.step = ConversationStep.AWAITING_PHOTO
    for control in ("yes", "No"):
        service.handle_message(session.phone, control)
        assert session.photo_resolved is False
        assert session.raw_citizen_text == original_evidence

    service.handle_message(session.phone, "skip")
    assert session.photo_resolved is True
    assert session.raw_citizen_text == original_evidence


def test_f_english_yes_preserves_arabic_success_language(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = _ready_session("96170010006")
    store.set(session.phone, session)
    monkeypatch.setattr(
        wa_service, "create_report_from_whatsapp", lambda data: "CIV-000006"
    )

    reply = service.handle_message(session.phone, "Yes")
    assert "تم إرسال البلاغ بنجاح" in reply
    assert "submitted successfully" not in reply


def test_g_ai_filled_fields_still_require_photo_resolution():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170010007",
        language=SupportedLanguage.AR,
        description="Citizen report awaiting AI extraction.",
        raw_citizen_text="في حفرة كبيرة على طريق الحمرا",
    )
    service.apply_multimodal_result(session, _analysis())

    reply = service.decide_next_reply(session)
    assert session.issue_type == "pothole"
    assert session.location_text == "طريق الحمرا"
    assert session.ai_analyzed is True
    assert session.photo_resolved is False
    assert session.step == ConversationStep.AWAITING_PHOTO
    assert "صورة" in reply
    assert "ملخص البلاغ" not in reply
