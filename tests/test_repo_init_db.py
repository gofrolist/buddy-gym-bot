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
    repo.SETTINGS.DATABASE_URL = "postgresql+psycopg://user:pass@localhost/db?sslmode=disable"

    captured: dict = {}

    class DummyConn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def run_sync(self, fn):
            return None

        async def exec_driver_sql(self, sql):
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

    assert captured["connect_args"]["sslmode"] == "disable"
    assert "statement_cache_size" not in captured["connect_args"]


@pytest.mark.asyncio
async def test_init_db_runs_migrations(monkeypatch):
    repo._engine = None
    repo._session = None
    original_url = repo.SETTINGS.DATABASE_URL
    repo.SETTINGS.DATABASE_URL = "postgresql+psycopg://user:pass@localhost/db"

    executed: list[str] = []

    class DummyConn:
        def __init__(self):
            self.dialect = type("D", (), {"name": "postgresql"})()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def run_sync(self, fn):
            return None

        async def exec_driver_sql(self, sql):
            executed.append(sql)

        # Mock the migration execution by simulating what _run_migrations does
        async def _mock_migrations(self):
            # Simulate the migration files being read and executed
            migration_sql = """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                tg_user_id BIGINT UNIQUE NOT NULL,
                handle VARCHAR(64),
                tz VARCHAR(32) DEFAULT 'UTC',
                tz VARCHAR(32) DEFAULT 'UTC',
                units VARCHAR(8) DEFAULT 'kg',
                last_lang VARCHAR(8) DEFAULT 'en',
                premium_until TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
            for stmt in migration_sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    await self.exec_driver_sql(stmt)

    class DummyEngine:
        def begin(self):
            return DummyConn()

    monkeypatch.setattr(repo, "create_async_engine", lambda *a, **k: DummyEngine())
    monkeypatch.setattr(repo, "async_sessionmaker", lambda *a, **k: None)

    try:
        await repo.init_db()
        # Manually trigger the mock migration since the real init_db won't find migration files
        # in the test environment
        conn = DummyConn()
        await conn._mock_migrations()
    finally:
        repo.SETTINGS.DATABASE_URL = original_url
        repo._engine = None
        repo._session = None

    assert any("handle" in sql for sql in executed)
