import os

import httpx
import pytest  # pyright: ignore[reportMissingImports]

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "invalid-key")

from buddy_gym_bot.bot.openai_scheduling import generate_schedule


class UnauthorizedTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:  # type: ignore[override]
        return httpx.Response(401, json={"error": "Unauthorized"})


@pytest.mark.asyncio
async def test_generate_schedule_unauthorized(monkeypatch):
    transport = UnauthorizedTransport()
    orig_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)
    plan = await generate_schedule("test")
    assert plan["program_name"] == "Fallback Plan"
