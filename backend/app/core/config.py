from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    ENV: str = "development"
    APP_NAME: str = "CivicPulse AI"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "changeme-generate-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # --- Local dev admin seed (single-admin-role MVP, no RBAC) ---
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme123"

    # --- Database (PostgreSQL) ---
    DATABASE_URL: str = "postgresql+psycopg2://postgres:changeme@localhost:5432/civicpulse"

    # --- Redis (WhatsApp in-progress report sessions, caching) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    WHATSAPP_SESSION_TTL_SECONDS: int = 1800

    # --- WhatsApp Business API (via Twilio) ---
    WHATSAPP_PROVIDER: str = "twilio"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_BUSINESS_NUMBER: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""

    # --- AWS S3 (photo & voice note storage) ---
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "civicpulse-media-dev"

    # --- Whisper (speech-to-text) ---
    WHISPER_MODEL: str = "large-v3"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE_HINT: str = "auto"

    # --- Hugging Face / Transformers (classification + embeddings) ---
    HF_HOME: str = ".cache/huggingface"
    HF_CLASSIFICATION_MODEL: str = ""
    HF_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # --- Maps (Google Maps API / Mapbox) ---
    MAPS_PROVIDER: str = "mapbox"
    MAPS_API_KEY: str = ""


settings = Settings()
