from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Claude API (via local antigravity proxy)
    anthropic_api_key: str = "proxy"
    claude_proxy_url: str = "http://localhost:8080"

    # MLS API
    mls_api_base_url: str = "https://tfs.tlcengine.com/api"
    mls_api_token: str = ""

    # Close CRM
    close_api_key: str = ""

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://aiassistant:aiassistant123@localhost:5432/aiassistant"

    # Google OAuth (Dossier project creds)
    google_client_id: str = ""
    google_client_secret: str = ""

    # Email (Google Workspace SMTP for claude@certihomes.com)
    smtp_app_password: str = ""

    # TLCengine V3 API (CJMLS property portal backend)
    tlcengine_api_url: str = "https://api.tlcengine.com/V3/api/km"
    tlcengine_api_token: str = "C40A98B6-587C-481A-9FFB-A00E51E8D29A"

    # VoiceBox (local on geo2)
    voicebox_url: str = "http://127.0.0.1:17493"

    # Server
    host: str = "0.0.0.0"
    port: int = 8005

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
