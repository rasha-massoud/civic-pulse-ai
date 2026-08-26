import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.services.whatsapp.router import router as whatsapp_router

logging.basicConfig(
    level=logging.INFO if settings.ENV == "development" else logging.WARNING,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)

# Optional authenticated Hugging Face downloads (higher rate limits).
# Libraries that honor HUGGING_FACE_HUB_TOKEN / HF_TOKEN pick this up automatically.
if settings.HF_TOKEN.strip() and not os.environ.get("HF_TOKEN"):
    os.environ["HF_TOKEN"] = settings.HF_TOKEN.strip()

_preload_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper-preload")


def _run_whisper_preload() -> None:
    try:
        from app.services.ai.transcription import preload_whisper_model

        logger.info("WHISPER_PRELOAD=true — warming Whisper model in background")
        preload_whisper_model()
    except Exception:
        # Do not prevent the API from staying up if model load fails.
        logger.exception(
            "Whisper preload failed; voice notes will wait on first use or "
            "return a graceful retry if the model cannot load"
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # API/webhook become ready immediately; Whisper may still be warming.
    if settings.WHISPER_PRELOAD:
        _preload_executor.submit(_run_whisper_preload)
    yield
    _preload_executor.shutdown(wait=False)


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix=settings.API_V1_PREFIX)
app.include_router(whatsapp_router, prefix="/api/whatsapp", tags=["WhatsApp"])
