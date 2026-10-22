"""Settings status endpoint (never exposes secret values)."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsStatus(BaseModel):
    auth_enabled: bool
    gemini_model: str
    gemini_configured: bool
    firecrawl_configured: bool
    openai_configured: bool
    anthropic_configured: bool
    max_daily_scrape_credits: int


@router.get("", response_model=SettingsStatus)
def get_settings(request: Request) -> SettingsStatus:
    s = request.app.state.settings
    return SettingsStatus(
        auth_enabled=not s.auth_disabled,
        gemini_model=s.gemini_model,
        gemini_configured=bool(s.gemini_api_key),
        firecrawl_configured=bool(s.firecrawl_api_key),
        openai_configured=bool(s.openai_api_key),
        anthropic_configured=bool(s.anthropic_api_key),
        max_daily_scrape_credits=s.max_daily_scrape_credits,
    )
