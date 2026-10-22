from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings read from environment variables and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "production"] = "local"
    debug: bool = False
    port: int = 8000
    event_poll_seconds: float = 2.0  # Live feed: how often to check for new audit events.
    database_url: str = "sqlite:///./data/job_butler.db"
    artifacts_dir: Path = Path("artifacts")
    profile_path: Path = Path("profile/candidate_profile.yaml")

    firecrawl_api_key: str | None = None
    max_daily_scrape_credits: int = 100
    firecrawl_state_dir: Path = Path("data/firecrawl")  # Shared credit budget + 12h cache.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
