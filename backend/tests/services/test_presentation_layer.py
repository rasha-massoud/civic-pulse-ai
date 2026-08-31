"""Presentation-layer tests: English location display + citizen WhatsApp summary."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.location_display import display_location_en, ensure_english_places
from app.services.reports import create_report_from_intake
from app.services.whatsapp.schemas import ConversationStep, SupportedLanguage, WhatsAppReportData, WhatsAppSession
from app.services.whatsapp.service import WhatsAppConversationService
from app.services.whatsapp.session import InMemorySessionStore


def test_display_location_en_hamra_road():
    assert display_location_en("طريق الحمرا") == "Hamra Street"
    assert display_location_en("شارع الحمرا") == "Hamra Street"


def test_display_location_en_coastal_road():
    assert "Coastal Road" in display_location_en("الطريق البحري ببيروت")
    assert "Beirut" in display_location_en("الطريق البحري ببيروت")


def test_display_location_en_preserves_english():
    assert display_location_en("near AUB main gate") == "near AUB main gate"


def test_ensure_english_places_in_mixed_description():
    text = "A large pothole has been reported on طريق الحمرا."
    assert "طريق الحمرا" not in ensure_english_places(text, original_location="طريق الحمرا")
    assert "Hamra Street" in ensure_english_places(text, original_location="طريق الحمرا")


def test_persist_keeps_original_and_english_district():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    report = create_report_from_intake(
        db,
        WhatsAppReportData(
            reporter_phone="96170007777",
            issue_type="pothole",
            description="A large pothole has been reported on طريق الحمرا.",
            location_text="طريق الحمرا",
            language="ar",
            severity="medium",
            ai_summary="Pothole reported in طريق الحمرا",
            ai_confidence=0.8,
        ),
    )

    assert report.location_text == "طريق الحمرا"
    assert report.issue.district == "Hamra Street"
    assert "طريق" not in (report.transcribed_text or "")
    assert "Hamra Street" in (report.transcribed_text or "")
    assert report.ai_summary is not None
    assert "Hamra Street" in report.ai_summary
    assert report.ai_confidence == 0.8
    db.close()


def test_english_confirmation_hides_ai_metadata():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170008888",
        language=SupportedLanguage.EN,
        step=ConversationStep.AWAITING_CONFIRMATION,
        issue_type="water_leak",
        description="Significant water leak on Verdun Street.",
        raw_citizen_text="there is a big water leak on Verdun Street",
        citizen_issue_label="Water leak",
        citizen_summary="Significant water leak reported on Verdun Street.",
        location_text="Verdun Street",
        media_urls=["/uploads/reports/a.jpg"],
        conversation_history=[
            {"role": "citizen", "text": "there is a big water leak on Verdun Street"}
        ],
        ai_analyzed=True,
        ai_summary="Water leak on Verdun",
        ai_severity="high",
        ai_confidence=0.95,
        ai_uncertainties=["Source unclear"],
    )

    text = service._build_summary(session)
    assert "Report Summary" in text
    assert "Issue: Water leak" in text
    assert "Location: Verdun Street" in text
    assert "Photo: Attached" in text
    assert "Description" not in text
    assert "Significant water leak" not in text
    assert "AI Analysis" not in text
    assert "Confidence" not in text
    assert "Severity" not in text
    assert "0.95" not in text
    assert "Source unclear" not in text


def test_arabic_confirmation_hides_ai_metadata():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170009999",
        language=SupportedLanguage.AR,
        step=ConversationStep.AWAITING_CONFIRMATION,
        issue_type="pothole",
        description="Large pothole on Hamra Street.",
        raw_citizen_text="هناك حفرة كبيرة على طريق الحمرا",
        citizen_issue_label="حفرة كبيرة في الطريق",
        citizen_summary="توجد حفرة كبيرة على طريق الحمرا.",
        location_text="طريق الحمرا",
        media_urls=[],
        conversation_history=[
            {"role": "citizen", "text": "هناك حفرة كبيرة على طريق الحمرا"}
        ],
        ai_analyzed=True,
        ai_summary="Pothole reported in Hamra Street",
        ai_severity="medium",
        ai_confidence=0.7,
    )

    text = service._build_summary(session)
    assert "ملخص البلاغ" in text
    assert "المشكلة: حفرة في الطريق" in text
    assert "الموقع: طريق الحمرا" in text
    assert "الوصف" not in text
    assert "توجد حفرة" not in text
    assert "مرفقة" not in text  # no photos attached
    assert "تحليل" not in text
    assert "الثقة" not in text
    assert "الخطورة" not in text
    assert "0.7" not in text


def test_mixed_language_confirmation_uses_session_language():
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170001112",
        language=SupportedLanguage.EN,
        issue_type="pothole",
        location_text="Hamra Street",
        citizen_issue_label="Pothole",
        citizen_summary="Large pothole on Hamra Street.",
        photo_resolved=True,
        conversation_history=[
            {"role": "citizen", "text": "fi 7ofra kbire 3a tari2 hamra"}
        ],
        ai_analyzed=True,
        ai_summary="Pothole on Hamra Street",
        ai_confidence=0.8,
    )
    text = service.confirmation_reply(session)
    assert text.startswith("Report Summary")
    assert "Reply" in text or "yes" in text.lower()
    assert "Confidence" not in text
