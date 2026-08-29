from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    ENV: str = "development"
    APP_NAME: str = "CivicPulse AI"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "changeme-generate-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Local dev admin seed (single-admin-role MVP, no RBAC) ---
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme123"

    # --- Database (PostgreSQL) ---
    DATABASE_URL: str = "postgresql+psycopg2://postgres:changeme@localhost:5432/civicpulse"

    # --- Redis (WhatsApp in-progress report sessions, caching) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    WHATSAPP_SESSION_TTL_SECONDS: int = 1800

    # --- Meta WhatsApp Cloud API ---
    META_WHATSAPP_ACCESS_TOKEN: str = ""
    META_WHATSAPP_PHONE_NUMBER_ID: str = ""
    META_WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    META_WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    META_GRAPH_API_VERSION: str = "v23.0"

    # --- AWS S3 (photo & voice note storage) ---
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "civicpulse-media-dev"

    # --- Whisper (speech-to-text) ---
    # Model size is env-only (small / medium / …) — no code change needed to switch.
    # CPU MVP: DEVICE=cpu COMPUTE_TYPE=int8. GPU: cuda + float16 or int8_float16.
    WHISPER_MODEL: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    # Force language when set (e.g. "ar"). "auto" lets Whisper detect.
    WHISPER_LANGUAGE_HINT: str = "auto"
    # Optional domain bias for Lebanese municipal Arabic (empty = unused).
    WHISPER_INITIAL_PROMPT: str = ""
    # Beam search size (1 = greedy). Default 5 favors accuracy.
    WHISPER_BEAM_SIZE: int = 5
    # Silero VAD; short clips may auto-disable to avoid dropping speech.
    WHISPER_VAD_FILTER: bool = True
    WHISPER_PRELOAD: bool = False
    # After `python -m app.services.ai.prepare_whisper`, set True in production
    # so end-user voice notes never trigger a Hugging Face download.
    WHISPER_LOCAL_FILES_ONLY: bool = False
    # Max concurrent Whisper transcription jobs (CPU MVP: keep low; GPU can raise).
    WHISPER_MAX_CONCURRENT: int = 1
    # If WHISPER_DEVICE=cuda but CUDA is unavailable, fail unless this is true.
    WHISPER_ALLOW_CPU_FALLBACK: bool = False

    # --- Hugging Face / Transformers (classification + embeddings) ---
    HF_HOME: str = ".cache/huggingface"
    HF_TOKEN: str = ""
    HF_CLASSIFICATION_MODEL: str = ""
    HF_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # --- OpenAI (multimodal civic report analysis) ---
    OPENAI_API_KEY: str = ""
    OPENAI_MULTIMODAL_MODEL: str = "gpt-4o-mini"
    OPENAI_MULTIMODAL_TIMEOUT_SECONDS: float = 60.0

    # --- Maps (Google Maps API / Mapbox) ---
    MAPS_PROVIDER: str = "mapbox"
    MAPS_API_KEY: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _strip_cors_origins(cls, value: object) -> str:
        if value is None:
            return "http://localhost:5173"
        return str(value).strip()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
