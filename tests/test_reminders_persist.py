import os
import os
from datetime import datetime, timedelta
import types
import sys

import pytest

# ensure environment
os.environ.setdefault("BOT_TOKEN", "test-token")


class DummyBot:
    async def send_message(self, chat_id, text):
        pass


@pytest.mark.asyncio
async def test_reminders_persist_and_reload(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    # Stub config to avoid pydantic dependency
    config_stub = types.ModuleType("buddy_gym_bot.config")
    config_stub.SETTINGS = types.SimpleNamespace(
        BOT_TOKEN="test-token",
        DATABASE_URL=os.environ["DATABASE_URL"],
        FF_REFERRALS=False,
        FF_REMINDERS=True,
        USE_WEBHOOK=False,
        WEBAPP_URL="",
        FF_EXERCISEDB=False,
    )
    sys.modules["buddy_gym_bot.config"] = config_stub

    # Minimal aiogram stubs
    aiogram_stub = types.ModuleType("aiogram")
    class Bot: ...
    class Dispatcher: ...
    class Router: ...
    aiogram_stub.Bot = Bot
    aiogram_stub.Dispatcher = Dispatcher
    aiogram_stub.Router = Router
    client_default = types.ModuleType("aiogram.client.default")
    class DefaultBotProperties:  # pragma: no cover - simple stub
        def __init__(self, *a, **k): ...
    client_default.DefaultBotProperties = DefaultBotProperties
    enums = types.ModuleType("aiogram.enums")
    class ParseMode: HTML = "HTML"
    enums.ParseMode = ParseMode
    filters = types.ModuleType("aiogram.filters")
    class Command: 
        def __init__(self, *a, **k): ...
    class CommandStart(Command): ...
    filters.Command = Command
    filters.CommandStart = CommandStart
    types_mod = types.ModuleType("aiogram.types")
    class Message: ...
    types_mod.Message = Message
    sys.modules.update(
        {
            "aiogram": aiogram_stub,
            "aiogram.client": types.ModuleType("aiogram.client"),
            "aiogram.client.default": client_default,
            "aiogram.enums": enums,
            "aiogram.filters": filters,
            "aiogram.types": types_mod,
        }
    )

    # Stub other optional modules
    exdb_stub = types.ModuleType("buddy_gym_bot.exercisedb")
    class ExerciseDBClient: ...
    exdb_stub.ExerciseDBClient = ExerciseDBClient
    sys.modules["buddy_gym_bot.exercisedb"] = exdb_stub
    openai_stub = types.ModuleType("buddy_gym_bot.bot.openai_scheduling")
    async def generate_schedule(req, tz="UTC"): return {}
    openai_stub.generate_schedule = generate_schedule
    openai_stub.SETTINGS = types.SimpleNamespace(OPENAI_API_KEY=None)
    sys.modules["buddy_gym_bot.bot.openai_scheduling"] = openai_stub
    sys.modules["httpx"] = types.ModuleType("httpx")
    commands_stub = types.ModuleType("buddy_gym_bot.bot.commands_labels")
    async def apply_localized_commands(bot): ...
    commands_stub.apply_localized_commands = apply_localized_commands
    sys.modules["buddy_gym_bot.bot.commands_labels"] = commands_stub
    utils_stub = types.ModuleType("buddy_gym_bot.bot.utils")
    def wave_hello(name): return f"hi {name}"
    def webapp_button(url, label): return None
    utils_stub.wave_hello = wave_hello
    utils_stub.webapp_button = webapp_button
    sys.modules["buddy_gym_bot.bot.utils"] = utils_stub

    from buddy_gym_bot.db import repo
    from buddy_gym_bot.bot import main
    from buddy_gym_bot.db.models import Reminder
    from sqlalchemy import select

    # reset repo state
    repo._engine = None
    repo._session = None
    await repo.init_db()

    future = datetime.now() + timedelta(hours=3)
    plan = {
        "timezone": "UTC",
        "weeks": 1,
        "days": [
            {
                "weekday": main.WEEKDAYS[future.weekday()],
                "time": future.strftime("%H:%M"),
                "focus": "Test",
            }
        ],
    }

    bot = DummyBot()
    await main.schedule_plan_reminders(bot, 123, plan)

    # confirm reminders saved to DB
    sess = repo.get_session()
    async with sess() as s:
        res = await s.execute(select(Reminder))
        rows = res.scalars().all()
        assert rows
        saved_job_id = rows[0].job_id

    # simulate restart
    main.scheduler.remove_all_jobs()
    main.jobs_by_chat.clear()

    await main.load_reminders(bot)

    job_ids = {job.id for job in main.scheduler.get_jobs()}
    assert saved_job_id in job_ids
