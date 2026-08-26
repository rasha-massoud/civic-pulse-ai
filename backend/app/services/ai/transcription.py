"""Local speech-to-text via faster-whisper (CPU + optional NVIDIA GPU)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_load_error: Optional[str] = None
_effective_device: Optional[str] = None
_effective_compute_type: Optional[str] = None


class CudaUnavailableError(RuntimeError):
    """Raised when WHISPER_DEVICE=cuda but the host cannot use CUDA."""


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = None
    language_probability: Optional[float] = None


def whisper_model_name() -> str:
    return (settings.WHISPER_MODEL or "small").strip() or "small"


def whisper_device() -> str:
    return (settings.WHISPER_DEVICE or "cpu").strip().lower() or "cpu"


def whisper_compute_type() -> str:
    return (settings.WHISPER_COMPUTE_TYPE or "int8").strip() or "int8"


def whisper_download_root() -> Optional[str]:
    root = (settings.HF_HOME or "").strip()
    return root or None


def probe_cuda() -> dict:
    """Detect whether CTranslate2 (faster-whisper backend) can use NVIDIA CUDA."""
    try:
        import ctranslate2

        count = int(ctranslate2.get_cuda_device_count())
        supported: list[str] = []
        if count > 0:
            try:
                supported = sorted(ctranslate2.get_supported_compute_types("cuda"))
            except Exception:
                supported = []
        return {
            "available": count > 0,
            "device_count": count,
            "backend": "ctranslate2",
            "supported_compute_types": supported,
            "error": None
            if count > 0
            else (
                "No CUDA devices reported by CTranslate2. Install an NVIDIA driver "
                "and a CUDA-enabled CTranslate2 runtime on a GPU host."
            ),
        }
    except Exception as exc:
        return {
            "available": False,
            "device_count": 0,
            "backend": "ctranslate2",
            "supported_compute_types": [],
            "error": (
                f"CUDA/GPU runtime unavailable ({type(exc).__name__}: {exc}). "
                "This server is not GPU-capable for faster-whisper, or the CUDA "
                "CTranslate2 package/driver stack is missing."
            ),
        }


def resolve_runtime_device(
    *,
    allow_cpu_fallback: Optional[bool] = None,
) -> tuple[str, str]:
    """Resolve (device, compute_type) from settings + CUDA availability.

    Does not silently fall back to CPU unless WHISPER_ALLOW_CPU_FALLBACK=true.
    """
    requested = whisper_device()
    requested_compute = whisper_compute_type()
    fallback = (
        settings.WHISPER_ALLOW_CPU_FALLBACK
        if allow_cpu_fallback is None
        else allow_cpu_fallback
    )

    if requested in ("cuda", "gpu"):
        cuda = probe_cuda()
        if cuda["available"]:
            return "cuda", requested_compute

        message = (
            "WHISPER_DEVICE=cuda was requested but CUDA is not usable on this host. "
            f"{cuda.get('error') or 'No CUDA devices found.'} "
            "Use an NVIDIA GPU instance with driver + CUDA-enabled CTranslate2, "
            "or set WHISPER_DEVICE=cpu and WHISPER_COMPUTE_TYPE=int8. "
            "To allow automatic CPU fallback, set WHISPER_ALLOW_CPU_FALLBACK=true."
        )
        if fallback:
            logger.warning(
                "CUDA unavailable — falling back to CPU (WHISPER_ALLOW_CPU_FALLBACK=true) "
                "| reason=%s",
                cuda.get("error"),
            )
            return "cpu", "int8"
        raise CudaUnavailableError(message)

    # Explicit CPU (or any non-cuda value treated as CPU for safety)
    if requested != "cpu":
        logger.warning(
            "Unknown WHISPER_DEVICE=%s — using cpu. Supported values: cpu, cuda",
            requested,
        )
    return "cpu", requested_compute if requested == "cpu" else "int8"


def is_whisper_ready() -> bool:
    """True when a Whisper model instance is loaded in this process."""
    return _model is not None


def get_whisper_status() -> dict:
    """Readiness snapshot for health endpoints (no secrets)."""
    cuda = probe_cuda()
    requested_device = whisper_device()
    return {
        "ready": is_whisper_ready(),
        "model": whisper_model_name(),
        "requested_device": requested_device,
        "device": _effective_device or requested_device,
        "requested_compute_type": whisper_compute_type(),
        "compute_type": _effective_compute_type or whisper_compute_type(),
        "local_files_only": bool(settings.WHISPER_LOCAL_FILES_ONLY),
        "allow_cpu_fallback": bool(settings.WHISPER_ALLOW_CPU_FALLBACK),
        "cuda": {
            "available": cuda["available"],
            "device_count": cuda["device_count"],
            "backend": cuda["backend"],
            "supported_compute_types": cuda.get("supported_compute_types") or [],
            "error": cuda.get("error"),
        },
        "last_error": _load_error,
        "download_root": whisper_download_root(),
    }


def _create_whisper_model(*, local_files_only: bool):
    from faster_whisper import WhisperModel

    global _effective_device, _effective_compute_type

    model_name = whisper_model_name()
    device, compute_type = resolve_runtime_device()
    download_root = whisper_download_root()

    kwargs: dict = {
        "device": device,
        "compute_type": compute_type,
        "local_files_only": local_files_only,
    }
    if download_root:
        kwargs["download_root"] = download_root

    logger.info(
        "Whisper model loading... | model=%s device=%s compute_type=%s "
        "local_files_only=%s download_root=%s",
        model_name,
        device,
        compute_type,
        local_files_only,
        download_root or "(huggingface default cache)",
    )
    model = WhisperModel(model_name, **kwargs)
    _effective_device = device
    _effective_compute_type = compute_type
    logger.info(
        "Whisper model loaded successfully | model=%s device=%s compute_type=%s",
        model_name,
        device,
        compute_type,
    )
    return model


def _get_whisper_model():
    """Load Whisper once per process (thread-safe lazy singleton).

    In production, set WHISPER_LOCAL_FILES_ONLY=true after running
    ``python -m app.services.ai.prepare_whisper`` so end-user voice notes
    never trigger a Hugging Face download.
    """
    global _model, _load_error
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        local_only = bool(settings.WHISPER_LOCAL_FILES_ONLY)
        try:
            _model = _create_whisper_model(local_files_only=local_only)
            _load_error = None
            return _model
        except Exception as exc:
            _load_error = str(exc)
            logger.exception(
                "Whisper model load failed | model=%s local_files_only=%s",
                whisper_model_name(),
                local_only,
            )
            raise


def prepare_whisper_model(*, allow_download: bool = True) -> None:
    """Download/cache the configured model and verify it can be instantiated.

    Validates CUDA when WHISPER_DEVICE=cuda (unless CPU fallback is enabled).
    """
    global _model, _load_error

    # Fail fast with a clear message before attempting model download/load.
    resolve_runtime_device()

    with _model_lock:
        try:
            model = _create_whisper_model(local_files_only=not allow_download)
            _model = model
            _load_error = None
        except Exception as exc:
            _load_error = str(exc)
            raise


def preload_whisper_model() -> None:
    """Eagerly load Whisper from the prepared local cache when possible."""
    _get_whisper_model()


def reset_whisper_model() -> None:
    """Clear the cached model (tests / device switch)."""
    global _model, _load_error, _effective_device, _effective_compute_type
    with _model_lock:
        _model = None
        _load_error = None
        _effective_device = None
        _effective_compute_type = None


def _language_arg() -> Optional[str]:
    hint = (settings.WHISPER_LANGUAGE_HINT or "auto").strip().lower()
    if not hint or hint == "auto":
        return None
    return hint


def transcribe_audio(file_path: str) -> TranscriptionResult:
    """Transcribe an audio file to text (task=transcribe, not translate).

    Synchronous — call via ``asyncio.to_thread`` from async code.
    Concurrent callers share one model; use the WhatsApp voice semaphore to
    limit how many transcriptions run at once.
    """
    model = _get_whisper_model()
    language = _language_arg()

    logger.info("Whisper transcription started | path_suffix=%s", file_path[-12:])
    segments, info = model.transcribe(
        file_path,
        task="transcribe",
        language=language,
        vad_filter=True,
    )

    parts: list[str] = []
    for segment in segments:
        piece = (segment.text or "").strip()
        if piece:
            parts.append(piece)

    text = " ".join(parts).strip()
    detected_language = getattr(info, "language", None)
    probability = getattr(info, "language_probability", None)

    logger.info(
        "Whisper transcription complete | language=%s probability=%s text_len=%d",
        detected_language,
        round(float(probability), 3) if probability is not None else None,
        len(text),
    )

    return TranscriptionResult(
        text=text,
        language=detected_language,
        language_probability=float(probability) if probability is not None else None,
    )
