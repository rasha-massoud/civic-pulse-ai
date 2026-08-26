"""WhatsApp voice transcription + Meta webhook regression tests (mocked Meta/Whisper)."""

from __future__ import annotations

import app.services.whatsapp.router as wa_router
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai.transcription import TranscriptionResult
from app.services.whatsapp.idempotency import (
    MessageIdempotencyStore,
    set_idempotency_store,
)
from app.services.whatsapp.inbound import parse_meta_webhook
from app.services.whatsapp.language import format_location_text
from app.services.whatsapp.media import MediaDownload
from app.services.whatsapp.service import WhatsAppConversationService, voice_retry_message
from app.services.whatsapp.session import InMemorySessionStore, set_session_store
from app.services.whatsapp.schemas import SupportedLanguage


@pytest.fixture(autouse=True)
def _fresh_stores():
    set_session_store(InMemorySessionStore())
    set_idempotency_store(MessageIdempotencyStore())
    yield
    set_session_store(InMemorySessionStore())
    set_idempotency_store(MessageIdempotencyStore())


def _audio_payload(
    media_id: str = "test_audio_id",
    message_id: str = "wamid.AUDIO",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "96170000000",
                                    "id": message_id,
                                    "timestamp": "1",
                                    "type": "audio",
                                    "audio": {
                                        "id": media_id,
                                        "mime_type": "audio/ogg; codecs=opus",
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }


def _text_payload(body: str = "hi", message_id: str = "wamid.TEXT") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "96170000001",
                                    "id": message_id,
                                    "timestamp": "1",
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }


def test_parse_audio_extracts_media_id_and_mime():
    msgs = parse_meta_webhook(_audio_payload())
    assert len(msgs) == 1
    assert msgs[0].message_type == "audio"
    assert msgs[0].media_id == "test_audio_id"
    assert msgs[0].media_content_type and msgs[0].media_content_type.startswith("audio/ogg")


def test_arabic_transcript_enters_conversation_flow():
    arabic = "في حفرة كتير كبيرة بالحمرا"
    store = InMemorySessionStore()
    svc = WhatsAppConversationService(store=store)
    phone = "96171111111"

    greet = svc.handle_message(phone, "مرحبا")
    assert "بلاغ" in greet or "مشكلة" in greet or "CivicPulse" in greet

    reply = svc.handle_message(phone, arabic)
    session = store.get(phone)
    assert session is not None
    assert session.description == arabic
    assert session.issue_type == "pothole"
    assert "موقع" in reply or "وين" in reply or "located" in reply.lower()


def test_english_transcript_enters_conversation_flow():
    english = "There is a broken street light in Hamra"
    store = InMemorySessionStore()
    svc = WhatsAppConversationService(store=store)
    phone = "96172222222"

    svc.handle_message(phone, "hi")
    reply = svc.handle_message(phone, english)
    session = store.get(phone)
    assert session is not None
    assert session.issue_type == "street_light"
    assert "Where" in reply or "located" in reply.lower()


def test_audio_is_not_treated_as_photo_attachment():
    store = InMemorySessionStore()
    svc = WhatsAppConversationService(store=store)
    phone = "96173333333"
    svc.handle_message(phone, "hi")
    svc.handle_message(
        phone,
        "big pothole",
        media_id="voice123",
        media_content_type="audio/ogg",
    )
    session = store.get(phone)
    assert session is not None
    assert session.media_urls == []


def test_voice_retry_messages_bilingual():
    en = voice_retry_message(SupportedLanguage.EN)
    ar = voice_retry_message(SupportedLanguage.AR)
    assert "voice message" in en.lower()
    assert "الصوتية" in ar or "افهم" in ar


def test_webhook_ack_returns_immediately_without_waiting_on_whisper(monkeypatch):
    """POST webhook must acknowledge Meta even if background work is slow."""
    client = TestClient(app)
    scheduled: list = []

    async def fake_process(message):
        scheduled.append(message.message_id)

    monkeypatch.setattr(wa_router, "process_inbound_message", fake_process)

    response = client.post("/api/whatsapp/webhook", json=_audio_payload())
    assert response.status_code == 200
    assert response.json() == {"status": "received"}
    # TestClient runs BackgroundTasks before returning; ensure it was scheduled.
    assert scheduled == ["wamid.AUDIO"]


def test_webhook_audio_arabic_transcript(monkeypatch):
    client = TestClient(app)
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append((to, text))

    async def fake_transcribe(media_id: str, mime_type: str | None = None, message_id: str | None = None):
        assert media_id == "test_audio_id"
        return TranscriptionResult(
            text="في حفرة كتير كبيرة بالحمرا",
            language="ar",
            language_probability=0.9,
        )

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(wa_router, "transcribe_whatsapp_audio", fake_transcribe)

    response = client.post("/api/whatsapp/webhook", json=_audio_payload())
    assert response.status_code == 200
    assert sent
    assert sent[0][0] == "96170000000"
    assert "CivicPulse" in sent[0][1] or "بلدية" in sent[0][1] or "مشكلة" in sent[0][1]


def test_webhook_duplicate_message_id_skips_processing(monkeypatch):
    client = TestClient(app)
    sent: list[str] = []
    transcribe_calls: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    async def fake_transcribe(media_id: str, mime_type: str | None = None, message_id: str | None = None):
        transcribe_calls.append(media_id)
        return TranscriptionResult(text="pothole on hamra", language="en", language_probability=0.9)

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(wa_router, "transcribe_whatsapp_audio", fake_transcribe)

    payload = _audio_payload(message_id="wamid.TEST123")
    first = client.post("/api/whatsapp/webhook", json=payload)
    second = client.post("/api/whatsapp/webhook", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"status": "received"}
    assert second.json() == {"status": "received"}
    assert len(transcribe_calls) == 1
    assert len(sent) == 1


def test_webhook_failed_meta_download(monkeypatch):
    client = TestClient(app)
    sent: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    async def boom(media_id: str, mime_type: str | None = None, message_id: str | None = None):
        raise RuntimeError("download failed")

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(wa_router, "transcribe_whatsapp_audio", boom)

    response = client.post("/api/whatsapp/webhook", json=_audio_payload())
    assert response.status_code == 200
    assert sent
    assert "voice message" in sent[0].lower() or "الصوتية" in sent[0]


def test_webhook_empty_transcription(monkeypatch):
    client = TestClient(app)
    sent: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    async def empty(media_id: str, mime_type: str | None = None, message_id: str | None = None):
        return TranscriptionResult(text="   ", language="en", language_probability=0.1)

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(wa_router, "transcribe_whatsapp_audio", empty)

    response = client.post("/api/whatsapp/webhook", json=_audio_payload("empty_audio"))
    assert response.status_code == 200
    assert sent
    assert "voice message" in sent[0].lower() or "الصوتية" in sent[0]


def test_webhook_text_still_works(monkeypatch):
    client = TestClient(app)
    sent: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)

    response = client.post("/api/whatsapp/webhook", json=_text_payload("hi"))
    assert response.status_code == 200
    assert sent
    assert "CivicPulse" in sent[0] or "infrastructure" in sent[0].lower()


def test_webhook_image_and_location_still_parse():
    image_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "96170000002",
                                    "id": "wamid.IMG",
                                    "type": "image",
                                    "image": {
                                        "id": "IMG1",
                                        "mime_type": "image/jpeg",
                                        "caption": "pothole",
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }
    loc_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "96170000003",
                                    "id": "wamid.LOC",
                                    "type": "location",
                                    "location": {
                                        "latitude": 33.8967,
                                        "longitude": 35.4822,
                                        "name": "Hamra Street",
                                        "address": "Beirut",
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }
    img = parse_meta_webhook(image_payload)[0]
    loc = parse_meta_webhook(loc_payload)[0]
    assert img.media_id == "IMG1" and img.body == "pothole"
    assert format_location_text(
        name=loc.location_name,
        address=loc.location_address,
        latitude=loc.latitude,
        longitude=loc.longitude,
    ) == "Hamra Street, Beirut, 33.8967, 35.4822"


def test_status_only_webhook_ok():
    client = TestClient(app)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {"statuses": [{"id": "wamid.1", "status": "delivered"}]},
                    }
                ]
            }
        ],
    }
    assert client.post("/api/whatsapp/webhook", json=payload).status_code == 200


def test_failed_processing_allows_retry(monkeypatch):
    """mark_failed clears processing state so a Meta retry can re-acquire."""
    client = TestClient(app)
    attempts: list[int] = []

    async def boom_then_ok(message):
        attempts.append(1)
        if len(attempts) == 1:
            # Simulate worker failure path used by process_inbound_message.
            get_store = __import__(
                "app.services.whatsapp.idempotency", fromlist=["get_idempotency_store"]
            ).get_idempotency_store
            get_store().mark_failed(message.message_id)
            raise RuntimeError("temporary failure")

    monkeypatch.setattr(wa_router, "process_inbound_message", boom_then_ok)

    payload = _audio_payload(message_id="wamid.RETRY1")
    # First request schedules task; TestClient runs it and it fails/marks failed.
    # We call process directly via background — TestClient will raise if background raises.
    # So instead test the store API + acquire semantics directly.
    store = MessageIdempotencyStore()
    assert store.try_acquire("wamid.RETRY1") is True
    assert store.try_acquire("wamid.RETRY1") is False
    store.mark_failed("wamid.RETRY1")
    assert store.try_acquire("wamid.RETRY1") is True
    store.mark_completed("wamid.RETRY1")
    assert store.try_acquire("wamid.RETRY1") is False


def test_transcribe_whatsapp_audio_uses_tempfile_and_whisper(monkeypatch):
    import asyncio

    from app.services.whatsapp import voice as voice_mod

    async def fake_download(media_id: str):
        return MediaDownload(
            content=b"fake-ogg-bytes",
            mime_type="audio/ogg",
            media_id=media_id,
        )

    def fake_transcribe(path: str):
        assert path.endswith(".ogg")
        with open(path, "rb") as fh:
            assert fh.read() == b"fake-ogg-bytes"
        return TranscriptionResult(text="hello from voice", language="en", language_probability=0.8)

    monkeypatch.setattr(voice_mod, "download_media", fake_download)
    monkeypatch.setattr(voice_mod, "transcribe_audio", fake_transcribe)

    result = asyncio.run(voice_mod.transcribe_whatsapp_audio("mid1", "audio/ogg", message_id="wamid.1"))
    assert result.text == "hello from voice"
