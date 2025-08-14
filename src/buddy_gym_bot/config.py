import os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional

def _bool(name: str, default: bool) -> bool:
    """
    Helper to parse boolean environment variables.
    Accepts: 1, true, yes, on (case-insensitive).
    """
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")

def _norm_db_url(url: Optional[str]) -> Optional[str]:
    """
    Normalize database URL to use asyncpg driver for SQLAlchemy.
    """
    if not url:
        return None
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url

class Config(BaseSettings):
    """
    Application configuration loaded from environment variables.
    Uses pydantic for validation and parsing.
    """
    BOT_TOKEN: str = Field(..., description="Telegram bot token")
    ADMIN_CHAT_ID: Optional[int] = Field(None, description="Admin chat ID")
    DATABASE_URL: str = Field(..., description="Database URL")
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key")
    WEBAPP_URL: str = Field("https://buddy-gym-bot.fly.dev/webapp/", description="Webapp URL")

    EXERCISEDB_BASE_URL: str = Field("https://exercisedb.dev/api/v1", description="ExerciseDB base URL")
    EXERCISEDB_RAPIDAPI_KEY: Optional[str] = Field(None, description="ExerciseDB RapidAPI key")
    EXERCISEDB_RAPIDAPI_HOST: str = Field("exercisedb.p.rapidapi.com", description="ExerciseDB RapidAPI host")

    # Feature flags
    FF_AUTO_I18N: bool = Field(default_factory=lambda: _bool("FF_AUTO_I18N", True), description="Auto i18n feature flag")
    FF_REFERRALS: bool = Field(default_factory=lambda: _bool("FF_REFERRALS", True), description="Referrals feature flag")
    FF_REMINDERS: bool = Field(default_factory=lambda: _bool("FF_REMINDERS", True), description="Reminders feature flag")
    FF_SHARE_PNG: bool = Field(default_factory=lambda: _bool("FF_SHARE_PNG", True), description="Share PNG feature flag")
    FF_ADMIN_ALERTS: bool = Field(default_factory=lambda: _bool("FF_ADMIN_ALERTS", True), description="Admin alerts feature flag")
    FF_EXERCISEDB: bool = Field(default_factory=lambda: _bool("FF_EXERCISEDB", True), description="ExerciseDB feature flag")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL environment variable is required")
        return _norm_db_url(v)

    @field_validator("BOT_TOKEN")
    @classmethod
    def bot_token_required(cls, v):
        if not v:
            raise ValueError("BOT_TOKEN environment variable is required")
        return v

SETTINGS = Config()
