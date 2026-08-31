"""Regression: garbled Whisper must not drive confirmation; validate locations."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.ai.multimodal import (
    MultimodalReportAnalyzer,
    MultimodalReportInput,
    ReportImage,
    StructuredCivicReport,
)
from app.services.location_quality import is_meaningful_location
from app.services.whatsapp.classifier import classify_issue
from app.services.whatsapp.schemas import ConversationStep, SupportedLanguage, WhatsAppSession
from app.services.whatsapp.service import WhatsAppConversationService
from app.services.whatsapp.session import InMemorySessionStore

# Exact real-world failure transcript from production logs.
GARBLED_WHISPER = "لس بيلم ساكرة طريقة على صديقه"


def _garbage_analysis(**overrides) -> StructuredCivicReport:
    data = {
        "category": "garbage",
        "severity": "medium",
        "language": "ar-lb",
        "summary": "Garbage accumulation along a road",
        "description": (
            "A large pile of garbage is accumulated along the roadside and "
            "partially obstructs it."
        ),
        "citizen_issue_label": "تراكم نفايات على الطريق",
        "citizen_summary": (
            "توجد كمية كبيرة من النفايات المتراكمة على جانب الطريق وتعيق جزءاً منه."
        ),
        "location_text": None,  # garbled transcript had no real place
        "latitude": None,
        "longitude": None,
        "image_findings": [
            {
                "image_index": 1,
                "observation": "Large accumulation of garbage along the road.",
                "supports_report": True,
            }
        ],
        "uncertainties": ["Exact street name was not provided."],
        "confidence": 0.88,
    }
    data.update(overrides)
    return StructuredCivicReport.model_validate(data)


def test_tariqa_does_not_keyword_match_as_road_damage():
    """Substring طريق inside طريقة must not classify as road_damage."""
    assert classify_issue(GARBLED_WHISPER) != "road_damage"
    assert classify_issue("ضرر في الطريق قرب الحمرا") == "road_damage"
    assert classify_issue("في حفرة على طريق الحمرا") == "pothole"


def test_generic_location_fragments_are_invalid():
    for fragment in ("طريق", "طريقة", "شارع", "road", "street", "near", "  طريق  "):
        assert is_meaningful_location(fragment) is False
    assert is_meaningful_location("طريق الحمرا") is True
    assert is_meaningful_location("near AUB main gate") is True
    assert is_meaningful_location("الطريق البحري ببيروت") is True


def test_analyzer_rejects_generic_model_location():
    result = _garbage_analysis(location_text="طريقة")
    responses = SimpleNamespace(
        parse=lambda **kwargs: SimpleNamespace(output_parsed=result)
    )
    analyzer = MultimodalReportAnalyzer(
        client=SimpleNamespace(responses=responses), model="test-model"
    )
    out = analyzer.analyze(
        MultimodalReportInput(
            citizen_text=GARBLED_WHISPER,
            images=[ReportImage(content=b"\xff\xd8\xffimage", mime_type="image/jpeg")],
        )
    )
    assert out.location_text is None


def test_garbled_whisper_plus_garbage_image_asks_for_location_not_bad_confirm():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170001234",
        language=SupportedLanguage.AR,
        step=ConversationStep.AWAITING_PHOTO,
        issue_type="road_damage",  # provisional wrong keyword path
        description=GARBLED_WHISPER,
        raw_citizen_text=GARBLED_WHISPER,
        location_text="طريقة",  # invalid fragment previously accepted
        media_urls=["/uploads/reports/garbage.jpg"],
        conversation_history=[{"role": "citizen", "text": GARBLED_WHISPER}],
    )
    store.set(session.phone, session)

    service.apply_multimodal_result(session, _garbage_analysis())

    assert session.raw_citizen_text == GARBLED_WHISPER
    assert session.issue_type == "garbage"
    assert session.location_text is None
    assert session.citizen_summary and "نفايات" in session.citizen_summary
    assert "لس بيلم" not in (session.citizen_summary or "")
    assert service.is_ready_for_confirmation(session) is False
    assert "location" in service.missing_required_fields(session)

    reply = service.confirmation_reply(session)
    assert "ملخص البلاغ" not in reply or "موقع أدق" in reply
    assert "موقع أدق" in reply or "الشارع" in reply
    assert GARBLED_WHISPER not in reply
    assert "طريقة" not in reply or "موقع" in reply


def test_confirmation_uses_polished_arabic_not_raw_whisper():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170001235",
        language=SupportedLanguage.AR,
        step=ConversationStep.AWAITING_CONFIRMATION,
        issue_type="garbage",
        description="Municipal English description of garbage on Hamra Street.",
        raw_citizen_text=GARBLED_WHISPER,
        citizen_issue_label="تراكم نفايات على الطريق",
        citizen_summary=(
            "توجد كمية كبيرة من النفايات المتراكمة على جانب الطريق وتعيق جزءاً منه."
        ),
        location_text="طريق الحمرا",
        media_urls=["/uploads/reports/garbage.jpg"],
        photo_resolved=True,
        conversation_history=[{"role": "citizen", "text": GARBLED_WHISPER}],
        ai_analyzed=True,
        ai_summary="Garbage piled on Hamra Street",
        ai_confidence=0.9,
    )

    assert service.is_ready_for_confirmation(session) is True
    text = service._build_summary(session)
    assert "ملخص البلاغ" in text
    assert "المشكلة: تراكم نفايات" in text
    assert "طريق الحمرا" in text
    assert "الوصف" not in text
    assert "توجد كمية كبيرة من النفايات" not in text
    assert "الصورة: مرفقة" in text
    assert GARBLED_WHISPER not in text
    assert "Confidence" not in text
    assert "0.9" not in text


def test_image_category_overrides_provisional_keyword():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170001236",
        language=SupportedLanguage.AR,
        issue_type="road_damage",
        raw_citizen_text=GARBLED_WHISPER,
        description=GARBLED_WHISPER,
        location_text="طريق الحمرا",
        media_urls=["/uploads/reports/g.jpg"],
    )
    service.apply_multimodal_result(session, _garbage_analysis(location_text="طريق الحمرا"))
    assert session.issue_type == "garbage"
    assert session.raw_citizen_text == GARBLED_WHISPER
