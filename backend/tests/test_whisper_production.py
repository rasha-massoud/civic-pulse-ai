"""Production-oriented Whisper readiness / concurrency tests (mocked)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import app.services.whatsapp.router as wa_router
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai import transcription as transcription_mod
from app.services.whatsapp.idempotency import MessageIdempotencyStore, set_idempotency_store
from app.services.whatsapp.media import MediaDownload
from app.services.whatsapp.session import InMemorySessionStore, set_session_store
from app.services.whatsapp import voice as voice_mod


@pytest.fixture(autouse=True)
def _fresh_stores():
    set_session_store(InMemorySessionStore())
    set_idempotency_store(MessageIdempotencyStore())
    transcription_mod.reset_whisper_model()
    voice_mod.reset_whisper_semaphore()
    yield
    transcription_mod.reset_whisper_model()
    voice_mod.reset_whisper_semaphore()
    set_session_store(InMemorySessionStore())
    set_idempotency_store(MessageIdempotencyStore())


def test_health_distinguishes_api_and_whisper_ready(monkeypatch):
    client = TestClient(app)

    class _FakeDB:
        def execute(self, *_a, **_k):
            return None

    def _fake_get_db():
        yield _FakeDB()

    from app.api.v1 import health as health_mod

    app.dependency_overrides[health_mod.get_db] = _fake_get_db
    try:
        monkeypatch.setattr(
            health_mod,
            "get_whisper_status",
            lambda: {
                "ready": False,
                "model": "small",
                "device": "cpu",
                "compute_type": "int8",
                "local_files_only": True,
                "last_error": None,
                "download_root": ".cache/huggingface",
            },
        )
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["api_ready"] is True
        assert body["whisper_ready"] is False
        assert body["status"] == "ok"
    finally:
        app.dependency_overrides.clear()


def test_prepare_whisper_success_uses_configured_model(monkeypatch):
    created: list[bool] = []

    def fake_create(*, local_files_only: bool):
        created.append(local_files_only)
        return MagicMock(name="WhisperModel")

    monkeypatch.setattr(transcription_mod, "_create_whisper_model", fake_create)
    transcription_mod.prepare_whisper_model(allow_download=True)
    # allow_download=True → local_files_only=False (may download/cache)
    assert created == [False]
    assert transcription_mod.is_whisper_ready() is True


def test_prepare_whisper_failure_surfaces(monkeypatch):
    def boom(*, local_files_only: bool):
        raise RuntimeError("cache missing")

    monkeypatch.setattr(transcription_mod, "_create_whisper_model", boom)
    with pytest.raises(RuntimeError, match="cache missing"):
        transcription_mod.prepare_whisper_model(allow_download=False)
    assert transcription_mod.is_whisper_ready() is False
    assert transcription_mod.get_whisper_status()["last_error"]


def test_cpu_configuration_resolves_int8(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_DEVICE", "cpu")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_COMPUTE_TYPE", "int8")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_ALLOW_CPU_FALLBACK", False)

    device, compute = transcription_mod.resolve_runtime_device()
    assert device == "cpu"
    assert compute == "int8"

    status = transcription_mod.get_whisper_status()
    assert status["requested_device"] == "cpu"
    assert status["requested_compute_type"] == "int8"
    assert status["allow_cpu_fallback"] is False
    assert "cuda" in status
    assert "available" in status["cuda"]
    assert "device_count" in status["cuda"]


def test_cuda_requested_but_unavailable_fails(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_DEVICE", "cuda")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_COMPUTE_TYPE", "float16")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_ALLOW_CPU_FALLBACK", False)
    monkeypatch.setattr(
        transcription_mod,
        "probe_cuda",
        lambda: {
            "available": False,
            "device_count": 0,
            "backend": "ctranslate2",
            "supported_compute_types": [],
            "error": "No CUDA devices reported by CTranslate2.",
        },
    )

    with pytest.raises(transcription_mod.CudaUnavailableError, match="not usable"):
        transcription_mod.resolve_runtime_device()

    with pytest.raises(transcription_mod.CudaUnavailableError, match="GPU-capable|not usable"):
        transcription_mod.prepare_whisper_model(allow_download=True)

    assert transcription_mod.is_whisper_ready() is False


def test_cuda_unavailable_explicit_cpu_fallback(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_DEVICE", "cuda")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_COMPUTE_TYPE", "float16")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_ALLOW_CPU_FALLBACK", True)
    monkeypatch.setattr(
        transcription_mod,
        "probe_cuda",
        lambda: {
            "available": False,
            "device_count": 0,
            "backend": "ctranslate2",
            "supported_compute_types": [],
            "error": "No CUDA devices reported by CTranslate2.",
        },
    )

    device, compute = transcription_mod.resolve_runtime_device()
    assert device == "cpu"
    assert compute == "int8"


def test_cuda_available_keeps_float16(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_DEVICE", "cuda")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_COMPUTE_TYPE", "float16")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_ALLOW_CPU_FALLBACK", False)
    monkeypatch.setattr(
        transcription_mod,
        "probe_cuda",
        lambda: {
            "available": True,
            "device_count": 1,
            "backend": "ctranslate2",
            "supported_compute_types": ["float16", "int8"],
            "error": None,
        },
    )

    device, compute = transcription_mod.resolve_runtime_device()
    assert device == "cuda"
    assert compute == "float16"


def test_health_includes_cuda_device_details(monkeypatch):
    client = TestClient(app)

    class _FakeDB:
        def execute(self, *_a, **_k):
            return None

    def _fake_get_db():
        yield _FakeDB()

    from app.api.v1 import health as health_mod

    app.dependency_overrides[health_mod.get_db] = _fake_get_db
    try:
        monkeypatch.setattr(
            health_mod,
            "get_whisper_status",
            lambda: {
                "ready": True,
                "model": "small",
                "requested_device": "cuda",
                "device": "cuda",
                "requested_compute_type": "float16",
                "compute_type": "float16",
                "local_files_only": True,
                "allow_cpu_fallback": False,
                "cuda": {
                    "available": True,
                    "device_count": 1,
                    "backend": "ctranslate2",
                    "supported_compute_types": ["float16"],
                    "error": None,
                },
                "last_error": None,
                "download_root": ".cache/huggingface",
            },
        )
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["whisper_ready"] is True
        assert body["whisper"]["device"] == "cuda"
        assert body["whisper"]["cuda"]["available"] is True
        assert body["whisper"]["cuda"]["device_count"] == 1
        assert "META_WHATSAPP_ACCESS_TOKEN" not in str(body)
        assert "HF_TOKEN" not in str(body)
        assert "SECRET_KEY" not in str(body)
    finally:
        app.dependency_overrides.clear()


def test_model_already_cached_local_files_only(monkeypatch):
    """Runtime load with local_files_only=True uses existing cache only."""
    created: list[bool] = []

    def fake_create(*, local_files_only: bool):
        created.append(local_files_only)
        return MagicMock(name="WhisperModel")

    monkeypatch.setattr(transcription_mod, "_create_whisper_model", fake_create)
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_LOCAL_FILES_ONLY", True)

    model = transcription_mod._get_whisper_model()
    assert model is not None
    assert created == [True]
    assert transcription_mod.is_whisper_ready() is True


def test_voice_while_model_initializing_waits_then_succeeds(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_download(media_id: str):
        return MediaDownload(content=b"ogg", mime_type="audio/ogg", media_id=media_id)

    def slow_transcribe(path: str):
        # Block until test releases — simulates waiting on model init / CPU work.
        started.set()
        # Can't wait on asyncio.Event from sync thread easily; just succeed.
        return transcription_mod.TranscriptionResult(
            text="pothole in hamra",
            language="en",
            language_probability=0.9,
        )

    monkeypatch.setattr(voice_mod, "download_media", fake_download)
    monkeypatch.setattr(voice_mod, "transcribe_audio", slow_transcribe)

    result = asyncio.run(
        voice_mod.transcribe_whatsapp_audio("mid", "audio/ogg", "wamid.init")
    )
    assert "pothole" in result.text


def test_concurrency_limit_serializes_whisper_jobs(monkeypatch):
    voice_mod.reset_whisper_semaphore()
    voice_mod._whisper_semaphore = asyncio.Semaphore(1)

    active = 0
    max_active = 0

    async def fake_download(media_id: str):
        return MediaDownload(content=b"x", mime_type="audio/ogg", media_id=media_id)

    def fake_transcribe(path: str):
        return transcription_mod.TranscriptionResult(
            text="ok", language="en", language_probability=1.0
        )

    async def tracked_to_thread(fn, path):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        try:
            return fn(path)
        finally:
            active -= 1

    monkeypatch.setattr(voice_mod, "download_media", fake_download)
    monkeypatch.setattr(voice_mod, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(voice_mod.asyncio, "to_thread", tracked_to_thread)

    async def run_many():
        await asyncio.gather(
            voice_mod.transcribe_whatsapp_audio("a", "audio/ogg", "1"),
            voice_mod.transcribe_whatsapp_audio("b", "audio/ogg", "2"),
            voice_mod.transcribe_whatsapp_audio("c", "audio/ogg", "3"),
        )

    asyncio.run(run_many())
    assert max_active == 1


def test_text_still_works_when_whisper_unavailable(monkeypatch):
    client = TestClient(app)
    sent: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(
        transcription_mod,
        "_get_whisper_model",
        lambda: (_ for _ in ()).throw(RuntimeError("whisper unavailable")),
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "96170009999",
                                    "id": "wamid.TEXT.OK",
                                    "timestamp": "1",
                                    "type": "text",
                                    "text": {"body": "hi"},
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }
    response = client.post("/api/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert sent
    assert "CivicPulse" in sent[0] or "infrastructure" in sent[0].lower()


def test_voice_returns_retry_when_model_init_fails(monkeypatch):
    client = TestClient(app)
    sent: list[str] = []

    async def fake_send(to: str, text: str) -> None:
        sent.append(text)

    async def boom_transcribe(media_id: str, mime_type=None, message_id=None):
        raise RuntimeError("local_files_only: model not found")

    monkeypatch.setattr(wa_router, "send_text_message", fake_send)
    monkeypatch.setattr(wa_router, "transcribe_whatsapp_audio", boom_transcribe)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "96170008888",
                                    "id": "wamid.AUDIO.FAIL",
                                    "timestamp": "1",
                                    "type": "audio",
                                    "audio": {"id": "AUD1", "mime_type": "audio/ogg"},
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }
    response = client.post("/api/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert sent
    assert "voice message" in sent[0].lower() or "الصوتية" in sent[0]
