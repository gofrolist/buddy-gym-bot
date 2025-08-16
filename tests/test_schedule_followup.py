import copy
import os

import pytest

# Ensure required environment variables are set for config
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("FF_REMINDERS", "0")
os.environ.setdefault("FF_EXERCISEDB", "0")

from buddy_gym_bot.bot.main import cmd_schedule  # generate_schedule will be patched
from buddy_gym_bot.config import SETTINGS
from buddy_gym_bot.db import repo


class DummyUser:
    def __init__(self, id: int = 1, username: str = "tester", language_code: str = "en"):
        self.id = id
        self.username = username
        self.language_code = language_code


class DummyChat:
    id = 1


class DummyMessage:
    def __init__(self, text: str):
        self.text = text
        self.from_user = DummyUser()
        self.chat = DummyChat()
        self.bot = None
        self.replies: list[str] = []

    async def answer(self, text: str, reply_markup=None):
        self.replies.append(text)


@pytest.mark.asyncio
async def test_schedule_followup_changes_only_time(monkeypatch):
    plan_holder: dict[str, dict] = {}

    async def fake_upsert_user(user_id, username, language_code):
        class U:
            def __init__(self, id: int):
                self.id = id
                self.tz = "UTC"

        return U(user_id)

    async def fake_get_user_plan(user_id):
        return plan_holder.get("plan")

    async def fake_upsert_user_plan(user_id, plan):
        plan_holder["plan"] = plan

    monkeypatch.setattr(repo, "upsert_user", fake_upsert_user)
    monkeypatch.setattr(repo, "get_user_plan", fake_get_user_plan)
    monkeypatch.setattr(repo, "upsert_user_plan", fake_upsert_user_plan)
    monkeypatch.setattr(SETTINGS, "FF_REMINDERS", False)
    monkeypatch.setattr(SETTINGS, "FF_EXERCISEDB", False)

    async def fake_generate_schedule(text: str, tz: str = "UTC", base_plan: dict | None = None):
        if base_plan is None:
            return {
                "program_name": "TestPlan",
                "timezone": tz,
                "weeks": 1,
                "days_per_week": 2,
                "days": [
                    {"weekday": "Mon", "time": "08:00", "focus": "Full", "exercises": []},
                    {"weekday": "Thu", "time": "18:00", "focus": "Full", "exercises": []},
                ],
            }
        new_plan = copy.deepcopy(base_plan)
        for day in new_plan["days"]:
            if day["weekday"] == "Mon":
                day["time"] = "10:00"
        return new_plan

    monkeypatch.setattr("buddy_gym_bot.bot.main.generate_schedule", fake_generate_schedule)

    msg1 = DummyMessage("/schedule 2-day plan")
    await cmd_schedule(msg1)
    initial_plan = copy.deepcopy(plan_holder["plan"])

    msg2 = DummyMessage("/schedule change Monday time to 10:00")
    await cmd_schedule(msg2)
    updated_plan = plan_holder["plan"]

    assert updated_plan["days_per_week"] == 2
    initial_times = {d["weekday"]: d["time"] for d in initial_plan["days"]}
    updated_times = {d["weekday"]: d["time"] for d in updated_plan["days"]}
    assert updated_times["Mon"] == "10:00"
    assert updated_times["Thu"] == initial_times["Thu"]
