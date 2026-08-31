"""Multi-turn WhatsApp intake must merge evidence across messages."""

from __future__ import annotations

import asyncio

import app.services.whatsapp.router as wa_router
from app.services.ai.multimodal import StructuredCivicReport
from app.services.location_quality import is_meaningful_location
from app.services.whatsapp.schemas import ConversationStep, SupportedLanguage
from app.services.whatsapp.service import WhatsAppConversationService
from app.services.whatsapp.session import InMemorySessionStore, set_session_store


def _analysis(**overrides) -> StructuredCivicReport:
    data = {
        "category": "garbage",
        "severity": "medium",
        "language": "ar-lb",
        "summary": "Garbage blocking the street",
        "description": "Garbage is blocking the street in Sodeco.",
        "citizen_issue_label": "تراكم نفايات على الطريق",
        "citizen_summary": "في زبالة مسكرة الطريق في منطقة سوديكو.",
        "location_text": "سوديكو",
        "latitude": None,
        "longitude": None,
        "image_findings": [],
        "uncertainties": [],
        "confidence": 0.9,
    }
    data.update(overrides)
    return StructuredCivicReport.model_validate(data)


def test_neighborhood_names_are_meaningful_locations():
    for place in ("سوديكو", "بسوديكو", "الصوديكو", "Sodeco", "Hamra"):
        assert is_meaningful_location(place) is True
    assert is_meaningful_location("طريق") is False


def test_case1_issue_then_location_preserves_category(monkeypatch):
    """Msg1 issue + msg2 بسوديكو → garbage + Sodeco + description kept."""
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    calls: list[str] = []

    def fake_analyze(**kwargs):
        calls.append(kwargs.get("citizen_text") or "")
        text = kwargs.get("citizen_text") or ""
        if "بسوديكو" in text or "سوديكو" in text:
            return _analysis()
        return _analysis(
            location_text=None,
            citizen_summary="في زبالة مسكرة الطريق.",
            description="Garbage is blocking the street.",
        )

    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)

    phone = "96170003001"
    service.handle_message(phone, "في زبالة مسكرة الطريق")
    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))
    session = store.get(phone)
    assert session is not None
    assert session.issue_type == "garbage"
    assert session.step == ConversationStep.AWAITING_LOCATION
    first_summary = session.citizen_summary

    service.handle_message(phone, "بسوديكو")
    assert session.raw_citizen_text and "في زبالة مسكرة الطريق" in session.raw_citizen_text
    assert "بسوديكو" in session.raw_citizen_text
    assert session.ai_analyzed is False  # new evidence forces re-merge

    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))
    updated = store.get(phone)
    assert updated is not None
    assert updated.issue_type == "garbage"
    assert is_meaningful_location(updated.location_text)
    assert "سوديكو" in (updated.location_text or "") or "بسوديكو" in (
        updated.location_text or ""
    )
    assert updated.citizen_summary
    assert "معلومات كافية" not in (updated.citizen_summary or "")
    assert first_summary  # prior summary existed before follow-up
    assert len(calls) == 2
    assert "في زبالة مسكرة الطريق" in calls[1]
    assert "بسوديكو" in calls[1]

    set_session_store(InMemorySessionStore())


def test_case2_pothole_then_hamra_street(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    def fake_analyze(**kwargs):
        text = kwargs.get("citizen_text") or ""
        if "الحمرا" in text:
            return _analysis(
                category="pothole",
                summary="Large pothole on Hamra Street",
                description="A large pothole on Hamra Street.",
                citizen_issue_label="حفرة كبيرة",
                citizen_summary="في حفرة كبيرة على شارع الحمرا.",
                location_text="شارع الحمرا",
            )
        return _analysis(
            category="pothole",
            location_text=None,
            citizen_summary="في حفرة كبيرة.",
            description="A large pothole.",
            citizen_issue_label="حفرة كبيرة",
        )

    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)

    phone = "96170003002"
    service.handle_message(phone, "في حفرة كبيرة")
    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))
    service.handle_message(phone, "على شارع الحمرا")
    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))

    session = store.get(phone)
    assert session is not None
    assert session.issue_type == "pothole"
    assert "الحمرا" in (session.location_text or "")
    assert "حفرة" in (session.citizen_summary or session.description or "")

    set_session_store(InMemorySessionStore())


def test_case3_location_first_then_issue_detail(monkeypatch):
    """Msg1 vague+Sodeco, msg2 garbage detail → garbage + Sodeco."""
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    def fake_analyze(**kwargs):
        text = kwargs.get("citizen_text") or ""
        if "زبالة" in text:
            return _analysis()
        return _analysis(
            category="other",
            citizen_summary="في مشكلة في سوديكو.",
            description="An unspecified issue in Sodeco.",
            citizen_issue_label="مشكلة",
            location_text="سوديكو",
        )

    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)

    phone = "96170003003"
    service.handle_message(phone, "في مشكلة بسوديكو")
    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))
    session = store.get(phone)
    assert session is not None
    assert is_meaningful_location(session.location_text)

    service.handle_message(phone, "زبالة كتير مسكرة الطريق")
    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))

    updated = store.get(phone)
    assert updated is not None
    assert updated.issue_type == "garbage"
    assert is_meaningful_location(updated.location_text)
    assert "سوديكو" in (updated.raw_citizen_text or "") or "بسوديكو" in (
        updated.raw_citizen_text or ""
    )

    set_session_store(InMemorySessionStore())


def test_case4_complete_single_message_skips_separate_asks(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    monkeypatch.setattr(
        wa_router,
        "analyze_civic_report",
        lambda **kwargs: _analysis(),
    )

    phone = "96170003004"
    service.handle_message(phone, "في زبالة مسكرة الطريق بسوديكو")
    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))
    session = store.get(phone)
    assert session is not None
    assert session.issue_type == "garbage"
    assert is_meaningful_location(session.location_text)
    assert service.missing_required_fields(session) == []
    reply = service.reply_for_missing_fields(session)
    assert "موقع أدق" not in reply
    assert "ملخص البلاغ" in reply or "نعم" in reply or "skip" in reply.lower() or "تخطي" in reply

    set_session_store(InMemorySessionStore())


def test_case5_garbled_location_keeps_issue_asks_location(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    set_session_store(store)
    monkeypatch.setattr(wa_router, "conversation_service", service)

    def fake_analyze(**kwargs):
        return _analysis(
            location_text=None,
            citizen_summary="في زبالة مسكرة الطريق.",
            description="Garbage is blocking the street.",
            uncertainties=["Location spelling from speech was unclear."],
        )

    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)

    phone = "96170003005"
    service.handle_message(phone, "في زبالة مسكرة الطريق")
    asyncio.run(wa_router._ensure_analysis(phone, allow_early=True))

    # Follow-up is only a generic fragment — keep issue, ask for a real place.
    service.handle_message(phone, "طريق")
    updated = store.get(phone)
    assert updated is not None
    assert updated.issue_type == "garbage"
    assert "في زبالة مسكرة الطريق" in (updated.raw_citizen_text or "")
    assert "طريق" in (updated.raw_citizen_text or "")
    assert updated.citizen_summary
    assert "معلومات كافية" not in updated.citizen_summary
    assert "لا يوجد" not in updated.citizen_summary
    assert not is_meaningful_location(updated.location_text)
    assert "location" in service.missing_required_fields(updated)
    reply = service.reply_for_missing_fields(updated)
    assert "موقع أدق" in reply or "المنطقة" in reply
    assert "معلومات كافية" not in reply

    set_session_store(InMemorySessionStore())


def test_apply_multimodal_does_not_replace_good_fields_with_insufficient():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    from app.services.whatsapp.schemas import WhatsAppSession

    session = WhatsAppSession(
        phone="96170003006",
        language=SupportedLanguage.AR,
        issue_type="garbage",
        description="Garbage is blocking the street.",
        raw_citizen_text="في زبالة مسكرة الطريق\nبسوديكو",
        citizen_summary="في زبالة مسكرة الطريق.",
        citizen_issue_label="تراكم نفايات",
        location_text="سوديكو",
    )
    store.set(session.phone, session)

    bad = _analysis(
        category="other",
        citizen_summary="لا يوجد معلومات كافية",
        description="Not enough information.",
        citizen_issue_label="غير كافٍ",
        location_text=None,
    )
    service.apply_multimodal_result(session, bad)

    assert session.issue_type == "garbage"
    assert session.citizen_summary == "في زبالة مسكرة الطريق."
    assert session.location_text == "سوديكو"
    assert session.description == "Garbage is blocking the street."
