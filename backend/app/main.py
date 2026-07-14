import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.services.whatsapp.router import router as whatsapp_router

logging.basicConfig(
    level=logging.INFO if settings.ENV == "development" else logging.WARNING,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix=settings.API_V1_PREFIX)
app.include_router(whatsapp_router, prefix="/api/whatsapp", tags=["WhatsApp"])
