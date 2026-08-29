"""Tests for the WhatsApp -> multimodal -> session integration boundary."""

from __future__ import annotations

import asyncio

import app.services.whatsapp.router as wa_router
from app.services.ai.multimodal import StructuredCivicReport
from app.services.whatsapp.media import MediaDownload
from app.services.whatsapp.schemas import ConversationStep, WhatsAppSession
from app.services.whatsapp.service import WhatsAppConversationService
from app.services.whatsapp.session import InMemorySessionStore


def _analysis() -> StructuredCivicReport:
    return StructuredCivicReport(
        category="water_leak",
        severity="high",
        language="mixed",
        summary="Active water leak reported in Hamra",
        description="The citizen reports flowing water and the image shows water across the road.",
        location_text="Hamra Street, Beirut",
        latitude=33.8967,
        longitude=35.4822,
        image_findings=[
            {
                "image_index": 1,
                "observation": "Water is visible across part of the road.",
                "supports_report": True,
            }
        ],
        uncertainties=["The source of the leak is not visible."],
        confidence=0.92,
    )


def test_analyze_session_combines_transcript_image_location_and_conversation(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    monkeypatch.setattr(wa_router, "conversation_service", service)
    session = WhatsAppSession(
        phone="96170000000",
        step=ConversationStep.AWAITING_CONFIRMATION,
        description="fi may 3am temshe 3al tari2",
        location_text="Hamra Street, Beirut",
        latitude=33.8967,
        longitude=35.4822,
        media_urls=["meta:image-1"],
        conversation_history=[
            {"role": "citizen", "text": "fi may 3am temshe 3al tari2"}
        ],
    )
    store.set(session.phone, session)
    captured = {}

    async def fake_download(media_id: str):
        assert media_id == "image-1"
        return MediaDownload(
            content=b"\xff\xd8\xffimage bytes", mime_type="image/jpeg", media_id=media_id
        )

    def fake_analyze(**kwargs):
        captured.update(kwargs)
        return _analysis()

    monkeypatch.setattr(wa_router, "download_media", fake_download)
    monkeypatch.setattr(wa_router, "analyze_civic_report", fake_analyze)

    asyncio.run(wa_router._analyze_session(session))

    saved = store.get(session.phone)
    assert saved is not None and saved.ai_analyzed is True
    assert saved.issue_type == "water_leak"
    assert saved.ai_severity == "high"
    assert saved.ai_summary == "Active water leak reported in Hamra"
    assert captured["citizen_text"] == "fi may 3am temshe 3al tari2"
    assert captured["location"].latitude == 33.8967
    assert captured["images"][0].content == b"\xff\xd8\xffimage bytes"
    assert captured["conversation"][0].role == "citizen"


def test_confirmed_ai_result_maps_to_persistence_payload(monkeypatch):
    store = InMemorySessionStore()
    service = WhatsAppConversationService(store=store)
    session = WhatsAppSession(
        phone="96170000000",
        step=ConversationStep.AWAITING_CONFIRMATION,
        language="en",
        media_urls=["meta:image-1"],
    )
    service.apply_multimodal_result(session, _analysis())
    captured = {}

    def fake_create(data):
        captured["data"] = data
        return "CIV-000123"

    monkeypatch.setattr(
        "app.services.whatsapp.service.create_report_from_whatsapp", fake_create
    )

    reply = service.handle_message(session.phone, "yes")

    data = captured["data"]
    assert data.issue_type == "water_leak"
    assert data.severity == "high"
    assert (data.latitude, data.longitude) == (33.8967, 35.4822)
    assert "CIV-000123" in reply
    assert store.get(session.phone) is None
