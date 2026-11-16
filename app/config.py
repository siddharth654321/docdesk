# app/config.py
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the project root, not the current working directory,
# so settings load the same way no matter where the server is launched from.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Real environment variables win over .env, which wins over the defaults below.
    # extra="ignore": unrelated variables in .env must not crash startup.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    app_name: str = "DocDesk"
    api_key: str = "dev-key"  # overridden by API_KEY in the environment
    max_page_size: int = 100  # upper bound for GET /tickets?limit=


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it."""
    return Settings()
