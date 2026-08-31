"""Compare Whisper transcription quality/latency on the same audio file.

Standalone tool — does not touch WhatsApp webhooks or conversation logic.

Usage (from backend/, with venv active):

    python -m app.services.ai.compare_transcription path/to/voice.ogg
    python -m app.services.ai.compare_transcription path/to/voice.ogg --models small,medium
    python -m app.services.ai.compare_transcription path/to/voice.ogg --language ar

Uses current WHISPER_DEVICE / WHISPER_COMPUTE_TYPE / prompt / beam / VAD from env,
and only overrides WHISPER_MODEL (and optionally language) per run.

Prints full transcripts to stdout for local A/B comparison (not for production logs).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("compare_transcription")


@dataclass
class CompareRow:
    model: str
    language: Optional[str]
    language_probability: Optional[float]
    elapsed_ms: int
    text_len: int
    text: str
    error: Optional[str] = None


def _run_one(
    *,
    audio_path: str,
    model_name: str,
    language_hint: str,
) -> CompareRow:
    from app.core import config as config_mod
    from app.services.ai import transcription as transcription_mod

    # Override model/language for this run; keep device/compute/prompt/beam/vad.
    config_mod.settings.WHISPER_MODEL = model_name
    config_mod.settings.WHISPER_LANGUAGE_HINT = language_hint
    config_mod.settings.WHISPER_LOCAL_FILES_ONLY = False
    transcription_mod.reset_whisper_model()

    started = time.perf_counter()
    try:
        result = transcription_mod.transcribe_audio(audio_path)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CompareRow(
            model=model_name,
            language=result.language,
            language_probability=result.language_probability,
            elapsed_ms=elapsed_ms,
            text_len=len(result.text or ""),
            text=result.text or "",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("Transcription failed | model=%s", model_name)
        return CompareRow(
            model=model_name,
            language=None,
            language_probability=None,
            elapsed_ms=elapsed_ms,
            text_len=0,
            text="",
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        transcription_mod.reset_whisper_model()


def compare_models(
    audio_path: str,
    models: list[str],
    *,
    language_hint: str = "ar",
) -> list[CompareRow]:
    rows: list[CompareRow] = []
    for name in models:
        model_name = name.strip()
        if not model_name:
            continue
        logger.info("Comparing model=%s language_hint=%s path=%s", model_name, language_hint, audio_path)
        rows.append(
            _run_one(
                audio_path=audio_path,
                model_name=model_name,
                language_hint=language_hint,
            )
        )
    return rows


def _print_report(rows: list[CompareRow]) -> None:
    print()
    print("=" * 72)
    print("Whisper transcription comparison (same audio file)")
    print("=" * 72)
    for row in rows:
        print()
        print(f"--- model={row.model} ---")
        if row.error:
            print(f"ERROR: {row.error}")
            print(f"elapsed_ms={row.elapsed_ms}")
            continue
        print(f"language={row.language} probability={row.language_probability}")
        print(f"elapsed_ms={row.elapsed_ms} text_len={row.text_len}")
        print("transcript:")
        print(row.text)
    print()
    print("=" * 72)
    print("Summary")
    print("=" * 72)
    for row in rows:
        status = "FAIL" if row.error else "OK"
        print(
            f"  {row.model:10} {status:4}  {row.elapsed_ms:6} ms  "
            f"len={row.text_len}"
        )
    print()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare Whisper models on one audio file (quality + latency).",
    )
    parser.add_argument("audio_path", help="Path to audio file (ogg/wav/mp3/…)")
    parser.add_argument(
        "--models",
        default="small,medium",
        help="Comma-separated model sizes (default: small,medium)",
    )
    parser.add_argument(
        "--language",
        default="ar",
        help="WHISPER_LANGUAGE_HINT for every run (default: ar)",
    )
    args = parser.parse_args(argv)

    from pathlib import Path

    path = Path(args.audio_path)
    if not path.is_file():
        logger.error("Audio file not found: %s", path)
        return 1

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        logger.error("No models specified")
        return 1

    rows = compare_models(str(path), models, language_hint=args.language)
    _print_report(rows)
    return 1 if any(r.error for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
