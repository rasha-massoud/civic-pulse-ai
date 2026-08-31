"""Prepare / download the configured faster-whisper model for production.

Run during deployment BEFORE starting FastAPI so end-user voice notes never
trigger a Hugging Face download:

    cd backend
    .venv/bin/python -m app.services.ai.prepare_whisper

Reads WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
WHISPER_ALLOW_CPU_FALLBACK, HF_HOME, HF_TOKEN.

GPU example (small):

    WHISPER_MODEL=small
    WHISPER_DEVICE=cuda
    WHISPER_COMPUTE_TYPE=float16

GPU example (medium on 6GB, e.g. RTX 3050):

    WHISPER_MODEL=medium
    WHISPER_DEVICE=cuda
    WHISPER_COMPUTE_TYPE=int8_float16

CPU example:

    WHISPER_DEVICE=cpu
    WHISPER_COMPUTE_TYPE=int8
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("prepare_whisper")


def main() -> int:
    # Import after basicConfig so settings/env load with logging ready.
    from app.core.config import settings
    from app.services.ai.transcription import (
        CudaUnavailableError,
        prepare_whisper_model,
        probe_cuda,
        resolve_runtime_device,
        whisper_compute_type,
        whisper_device,
        whisper_download_root,
        whisper_model_name,
    )

    if settings.HF_TOKEN.strip() and not os.environ.get("HF_TOKEN"):
        os.environ["HF_TOKEN"] = settings.HF_TOKEN.strip()

    model = whisper_model_name()
    requested_device = whisper_device()
    requested_compute = whisper_compute_type()
    download_root = whisper_download_root()
    cuda = probe_cuda()

    logger.info(
        "Preparing Whisper model | model=%s requested_device=%s "
        "requested_compute_type=%s cache=%s cuda_available=%s cuda_devices=%s",
        model,
        requested_device,
        requested_compute,
        download_root or "(huggingface default cache)",
        cuda["available"],
        cuda["device_count"],
    )

    try:
        effective_device, effective_compute = resolve_runtime_device()
    except CudaUnavailableError as exc:
        logger.error("Whisper preparation FAILED | %s", exc)
        return 1

    logger.info(
        "Effective Whisper runtime | device=%s compute_type=%s "
        "(allow_cpu_fallback=%s)",
        effective_device,
        effective_compute,
        settings.WHISPER_ALLOW_CPU_FALLBACK,
    )

    try:
        prepare_whisper_model(allow_download=True)
    except CudaUnavailableError as exc:
        logger.error("Whisper preparation FAILED | %s", exc)
        return 1
    except Exception:
        logger.exception(
            "Whisper preparation FAILED | model=%s device=%s — fix "
            "network/disk/HF_TOKEN/GPU runtime and re-run before starting the API",
            model,
            effective_device,
        )
        return 1

    # Verify the prepared cache can be opened with local_files_only on the
    # same effective device/compute_type (including cuda+float16).
    try:
        prepare_whisper_model(allow_download=False)
    except Exception:
        logger.exception(
            "Whisper cache verification FAILED | model=%s device=%s was prepared "
            "but cannot be loaded with local_files_only=True",
            model,
            effective_device,
        )
        return 1

    logger.info(
        "Whisper preparation SUCCESS | model=%s device=%s compute_type=%s "
        "is cached and ready (set WHISPER_LOCAL_FILES_ONLY=true so API "
        "inference never downloads)",
        model,
        effective_device,
        effective_compute,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
