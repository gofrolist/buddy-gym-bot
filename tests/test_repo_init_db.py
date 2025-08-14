import os

import pytest

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from buddy_gym_bot.db import repo


@pytest.mark.asyncio
async def test_init_db_respects_ssl_disable(monkeypatch):
    # Reset state
    repo._engine = None
    repo._session = None
    original_url = repo.SETTINGS.DATABASE_URL
    repo.SETTINGS.DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/db?sslmode=disable"

    captured: dict = {}

    class DummyConn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def run_sync(self, fn):
            return None

    class DummyEngine:
        def begin(self):
            return DummyConn()

    def fake_create_async_engine(url, *args, **kwargs):
        captured["url"] = url
        captured["connect_args"] = kwargs.get("connect_args")
        return DummyEngine()

    monkeypatch.setattr(repo, "create_async_engine", fake_create_async_engine)

    try:
        await repo.init_db()
    finally:
        repo.SETTINGS.DATABASE_URL = original_url
        repo._engine = None
        repo._session = None

    assert captured["connect_args"]["ssl"] is False
    assert captured["connect_args"]["statement_cache_size"] == 0
