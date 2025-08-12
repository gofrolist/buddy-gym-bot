"""Tests for the /ask handler rate limit behavior."""

from __future__ import annotations

import asyncio
import os
import types

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from buddy_gym_bot.handlers import ask as ask_module


class DummyMessage:
    """Minimal Telegram message stub for handlers."""

    def __init__(self, text: str, user_id: int = 1) -> None:
        self.text = text
        self.from_user = types.SimpleNamespace(id=user_id)
        self.replies: list[str] = []
        self.bot = object()

    async def reply(self, text: str, **_: object) -> None:  # pragma: no cover - params unused
        self.replies.append(text)


class FakeRateLimitError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _setup_rate_limit(monkeypatch: pytest.MonkeyPatch, code: str) -> list[str]:
    """Prepare ask handler to raise a RateLimitError with given code and record alerts."""

    monkeypatch.setattr(ask_module, "RateLimitError", FakeRateLimitError)

    class FakeCompletions:
        def create(self, *args: object, **kwargs: object) -> object:
            raise FakeRateLimitError(code)

    class FakeClient:
        chat = types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(ask_module, "client", FakeClient())

    calls: list[str] = []

    async def fake_alert(bot: object, text: str) -> None:  # pragma: no cover - bot unused
        calls.append(text)

    monkeypatch.setattr(ask_module, "alert_admin", fake_alert)
    return calls


def test_rate_limit_insufficient_quota_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _setup_rate_limit(monkeypatch, "insufficient_quota")
    msg = DummyMessage("/ask hi")

    asyncio.run(ask_module.ask(msg))

    assert calls, "Expected alert_admin to be called for insufficient_quota"
    assert msg.replies and "try again" in msg.replies[0].lower()


def test_rate_limit_other_no_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _setup_rate_limit(monkeypatch, "other_code")
    msg = DummyMessage("/ask hi")

    asyncio.run(ask_module.ask(msg))

    assert not calls, "alert_admin should not be called for non-quota rate limits"
    assert msg.replies and "try again" in msg.replies[0].lower()
