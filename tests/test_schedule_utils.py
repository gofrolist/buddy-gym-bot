import os

import pytest

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from buddy_gym_bot.bot.main import _next_datetime_for


def test_next_datetime_valid() -> None:
    dt = _next_datetime_for("Mon", "12:00", "UTC")
    assert dt.weekday() == 0


def test_next_datetime_invalid_weekday() -> None:
    with pytest.raises(ValueError):
        _next_datetime_for("Funday", "12:00", "UTC")


def test_next_datetime_invalid_time() -> None:
    with pytest.raises(ValueError):
        _next_datetime_for("Mon", "24:61", "UTC")
