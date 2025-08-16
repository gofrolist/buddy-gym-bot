import os

import pytest

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from buddy_gym_bot.bot.main import cmd_track


class DummyUser:
    def __init__(self, id: int = 1, username: str = "tester", language_code: str = "en"):
        self.id = id
        self.username = username
        self.language_code = language_code


class DummyMessage:
    def __init__(self, text: str):
        self.text = text
        self.from_user = DummyUser()
        self.replies: list[str] = []

    async def reply(self, text: str, parse_mode: str | None = None) -> None:
        self.replies.append(text)


@pytest.mark.asyncio
async def test_cmd_track_negative_weight() -> None:
    msg = DummyMessage("/track bench -100x5")
    await cmd_track(msg)
    assert msg.replies and msg.replies[0].startswith("Usage: /track")


@pytest.mark.asyncio
async def test_cmd_track_negative_reps() -> None:
    msg = DummyMessage("/track bench 100x-5")
    await cmd_track(msg)
    assert msg.replies and msg.replies[0].startswith("Usage: /track")


@pytest.mark.asyncio
async def test_cmd_track_zero_weight() -> None:
    msg = DummyMessage("/track bench 0x5")
    await cmd_track(msg)
    assert msg.replies == ["Weight and reps must be greater than zero."]


@pytest.mark.asyncio
async def test_cmd_track_zero_reps() -> None:
    msg = DummyMessage("/track bench 100x0")
    await cmd_track(msg)
    assert msg.replies == ["Weight and reps must be greater than zero."]
