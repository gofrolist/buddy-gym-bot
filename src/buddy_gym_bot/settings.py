# src/buddy_gym_bot/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

# Load .env for local dev; in CI/Prod you'll use real env vars / GitHub Secrets
load_dotenv(override=False)


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str
    OPENAI_API_KEY: str
    DATABASE_URL: str
    REDIS_URL: str
    USE_WEBHOOK: bool
    WEBHOOK_URL: str
    PLAN_DEFAULT_SPLIT: str

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            DATABASE_URL=os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@localhost:5432/postgres",
            ),
            REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            USE_WEBHOOK=_to_bool(os.getenv("USE_WEBHOOK"), default=False),
            WEBHOOK_URL=os.getenv("WEBHOOK_URL", ""),
            PLAN_DEFAULT_SPLIT=os.getenv("PLAN_DEFAULT_SPLIT", "full_body"),
        )


settings = Settings.from_env()

# ---- Centralized OpenAI client (lazy) ---------------------------------------
# We create it on first use so importing settings never crashes tools/tests.
_openai_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    """Return a singleton OpenAI client, raising a clear error if key is missing."""
    global _openai_client
    if _openai_client is None:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your .env (local) "
                "or GitHub Secrets / Fly secrets (prod)."
            )
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client
