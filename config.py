from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Claude API
    anthropic_api_key: str = ""

    # MLS API
    mls_api_base_url: str = "https://tfs.tlcengine.com/api"
    mls_api_token: str = ""

    # Close CRM
    close_api_key: str = ""

    # VoiceBox
    voicebox_url: str = "http://localhost:8004"

    # Server
    host: str = "0.0.0.0"
    port: int = 8005

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
