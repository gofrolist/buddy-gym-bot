"""Regression tests for the /today handler."""

from __future__ import annotations

import types
from contextlib import asynccontextmanager
from datetime import date

import pytest

from buddy_gym_bot.handlers import plan as plan_module
from buddy_gym_bot.handlers import today as today_module


class DummyMessage:
    """Minimal Telegram message stub for handlers."""

    def __init__(self, text: str, user_id: int = 1) -> None:
        self.text = text
        self.from_user = types.SimpleNamespace(id=user_id)
        self.replies: list[str] = []

    async def reply(self, text: str, **_: object) -> None:  # pragma: no cover - params unused
        self.replies.append(text)


class FakeCursor:
    def __init__(self, plan: list[dict] | None) -> None:
        self._plan = plan

    async def fetchone(self) -> tuple[list[dict]] | None:
        return (self._plan,) if self._plan is not None else None


class FakeConn:
    def __init__(self) -> None:
        self.storage: dict[tuple[int, int, date], list[dict]] = {}

    async def execute(self, sql: str, params: tuple) -> FakeCursor | None:
        if sql.startswith("delete from workouts"):
            tg_user_id, week_start = params
            keys = [k for k in self.storage if k[0] == tg_user_id and k[2] == week_start]
            for k in keys:
                del self.storage[k]
            return None
        if sql.startswith("insert into workouts"):
            tg_user_id, day_of_week, plan, week_start = params
            self.storage[(tg_user_id, day_of_week, week_start)] = plan
            return None
        if sql.startswith("select plan from workouts"):
            tg_user_id, day_of_week, week_start = params
            plan = self.storage.get((tg_user_id, day_of_week, week_start))
            return FakeCursor(plan)
        raise AssertionError(f"Unexpected SQL: {sql}")


def test_today_after_plan_same_week(monkeypatch: pytest.MonkeyPatch) -> None:
    """/today should return a workout later in the same week as /plan."""

    fake_conn = FakeConn()

    @asynccontextmanager
    async def fake_get_conn():  # pragma: no cover - helper
        yield fake_conn

    monkeypatch.setattr(plan_module, "get_conn", fake_get_conn)
    monkeypatch.setattr(today_module, "get_conn", fake_get_conn)

    class FakeDate(date):
        _today = date(2024, 1, 1)  # Monday

        @classmethod
        def today(cls) -> date:
            return cls._today

    monkeypatch.setattr(plan_module, "date", FakeDate)
    monkeypatch.setattr(today_module, "date", FakeDate)

    async def run() -> None:
        # Create plan on Monday
        plan_msg = DummyMessage("/plan")
        await plan_module.plan(plan_msg)

        # Request today's workout on Wednesday of the same week
        FakeDate._today = date(2024, 1, 3)
        today_msg = DummyMessage("/today")
        await today_module.today(today_msg)

        assert today_msg.replies, "Expected a reply from /today"
        assert today_msg.replies[0].startswith("📋 *Today*"), today_msg.replies[0]

    import asyncio

    asyncio.run(run())
