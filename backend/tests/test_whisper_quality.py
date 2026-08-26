"""Unit tests for Whisper transcription quality decoding options."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.ai import transcription as transcription_mod


@pytest.fixture(autouse=True)
def _reset_model():
    transcription_mod.reset_whisper_model()
    yield
    transcription_mod.reset_whisper_model()


def test_language_hint_ar_passes_language_ar(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_LANGUAGE_HINT", "ar")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_INITIAL_PROMPT", "")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_BEAM_SIZE", 5)
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", False)
    monkeypatch.setattr(transcription_mod, "audio_duration_seconds", lambda _p: 5.0)

    kwargs = transcription_mod.build_transcribe_kwargs("clip.ogg")
    assert kwargs["task"] == "transcribe"
    assert kwargs["language"] == "ar"
    assert kwargs["beam_size"] == 5
    assert "initial_prompt" not in kwargs


def test_language_hint_auto_passes_none(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_LANGUAGE_HINT", "auto")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", False)
    kwargs = transcription_mod.build_transcribe_kwargs("clip.ogg")
    assert kwargs["language"] is None


def test_initial_prompt_passed_when_configured(monkeypatch):
    prompt = "حفرة، طريق، الحمرا، بيروت"
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_LANGUAGE_HINT", "ar")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_INITIAL_PROMPT", prompt)
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", False)

    kwargs = transcription_mod.build_transcribe_kwargs("clip.ogg")
    assert kwargs["initial_prompt"] == prompt


def test_empty_initial_prompt_omitted(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_INITIAL_PROMPT", "   ")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", False)
    kwargs = transcription_mod.build_transcribe_kwargs("clip.ogg")
    assert "initial_prompt" not in kwargs


def test_beam_size_configurable(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_BEAM_SIZE", 1)
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", False)
    kwargs = transcription_mod.build_transcribe_kwargs("clip.ogg")
    assert kwargs["beam_size"] == 1


def test_vad_disabled_for_short_audio(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", True)
    monkeypatch.setattr(transcription_mod, "audio_duration_seconds", lambda _p: 1.2)

    kwargs = transcription_mod.build_transcribe_kwargs("short.ogg")
    assert kwargs["vad_filter"] is False
    assert "vad_parameters" not in kwargs


def test_vad_enabled_with_gentle_params_for_longer_audio(monkeypatch):
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", True)
    monkeypatch.setattr(transcription_mod, "audio_duration_seconds", lambda _p: 4.0)

    kwargs = transcription_mod.build_transcribe_kwargs("longer.ogg")
    assert kwargs["vad_filter"] is True
    assert kwargs["vad_parameters"]["min_speech_duration_ms"] == 100


def test_transcribe_audio_does_not_normalize_text(monkeypatch):
    raw = "في حفرة كبيرة ع طريق الحمرا"

    fake_model = MagicMock()
    fake_segment = SimpleNamespace(text=f" {raw} ")
    fake_info = SimpleNamespace(language="ar", language_probability=0.97)
    fake_model.transcribe.return_value = ([fake_segment], fake_info)

    monkeypatch.setattr(transcription_mod, "_get_whisper_model", lambda: fake_model)
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_LANGUAGE_HINT", "ar")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_INITIAL_PROMPT", "")
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_BEAM_SIZE", 5)
    monkeypatch.setattr(transcription_mod.settings, "WHISPER_VAD_FILTER", False)

    result = transcription_mod.transcribe_audio("sample.ogg")
    assert result.text == raw
    assert result.language == "ar"

    call_kwargs = fake_model.transcribe.call_args.kwargs
    assert call_kwargs["task"] == "transcribe"
    assert call_kwargs["language"] == "ar"
    assert call_kwargs["beam_size"] == 5


def test_compare_models_runs_each_size(monkeypatch, tmp_path):
    from app.services.ai import compare_transcription as compare_mod

    audio = tmp_path / "sample.ogg"
    audio.write_bytes(b"fake")

    calls: list[str] = []

    def fake_run_one(*, audio_path: str, model_name: str, language_hint: str):
        calls.append(model_name)
        return compare_mod.CompareRow(
            model=model_name,
            language="ar",
            language_probability=0.9,
            elapsed_ms=10,
            text_len=5,
            text=f"text-{model_name}",
        )

    monkeypatch.setattr(compare_mod, "_run_one", fake_run_one)
    rows = compare_mod.compare_models(str(audio), ["small", "medium"], language_hint="ar")
    assert calls == ["small", "medium"]
    assert [r.model for r in rows] == ["small", "medium"]
    assert rows[0].text == "text-small"
