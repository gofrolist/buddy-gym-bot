from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import partial

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode

from ..config import SETTINGS
from ..logging_setup import setup_logging
from ..db import repo
from ..db.models import User
from .parsers import TRACK_RE
from .utils import webapp_button
from .commands_labels import apply_localized_commands
from .openai_scheduling import generate_schedule
from ..exercisedb import ExerciseDBClient

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

router = Router()
scheduler: AsyncIOScheduler | None = None

@router.message(CommandStart(deep_link=True))
async def cmd_start_dl(message: Message) -> None:
    """Handle /start with deep link."""
    await _handle_start(message)

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await _handle_start(message)

async def _handle_start(message: Message) -> None:
    """Upsert user and handle referral if present."""
    await repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.language_code)
    if SETTINGS.FF_REFERRALS and message.text and " " in message.text:
        payload = message.text.split(" ",1)[1].strip()
        if payload.startswith("ref_"):
            try:
                await repo.record_referral_click(message.from_user.id, payload)
            except Exception:
                logging.exception("record_referral_click failed")
    kb = webapp_button(SETTINGS.WEBAPP_URL, "Open BuddyGym")
    await message.answer("Welcome to BuddyGym! Track your workouts and get reminders.", reply_markup=kb)

@router.message(Command("track"))
async def cmd_track(message: Message) -> None:
    """Handle /track command for logging a workout set."""
    text = message.text or ""
    args = text.partition(" ")[2].strip()
    m = TRACK_RE.match(args)
    if not m:
        await message.reply("Usage: /track <exercise> <weight>x<reps> [rpeX]\nExample: /track bench 100x5 rpe8")
        return
    ex = m.group("ex")
    w = float(m.group("w"))
    r = int(m.group("r"))
    rpe = m.group("rpe")
    rpe_val = float(rpe) if rpe else None
    user = await repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.language_code)
    sess = await repo.start_session(user.id, title="Quick Log")
    row = await repo.append_set(sess.id, ex, w, r, rpe_val, is_warmup=False)
    if SETTINGS.FF_REFERRALS:
        try:
            ok = await repo.fulfil_referral_for_invitee(message.from_user.id)
            if ok:
                await message.answer("Referral fulfilled! +30 days Plus for both 🎉")
        except Exception:
            logging.exception("fulfil_referral_for_invitee failed")
    await message.answer(f"Logged: {ex} {w}x{r}" + (f" RPE{rpe_val:g}" if rpe_val else ""))

@router.message(Command("schedule"))
async def cmd_schedule(message: Message) -> None:
    """Handle /schedule command to generate a workout plan and schedule reminders."""
    req = (message.text or "").partition(" ")[2].strip() or "3 days/week, 40 minutes, dumbbells only"
    tz = "UTC"
    try:
        u = await repo.get_user_by_tg(message.from_user.id)
        if u and u.tz:
            tz = u.tz
    except Exception as e:
        logging.warning("Failed to get user timezone: %s", e)
    plan = await generate_schedule(req, tz=tz)

    # Optionally enrich with ExerciseDB
    if SETTINGS.FF_EXERCISEDB:
        try:
            client = ExerciseDBClient()
            plan = await client.map_plan_exercises(plan)
        except Exception:
            logging.exception("ExerciseDB enrichment failed")

    # Schedule reminders 60 minutes before each day/time
    if SETTINGS.FF_REMINDERS:
        try:
            await schedule_plan_reminders(message.bot, message.chat.id, plan)
        except Exception:
            logging.exception("Scheduling reminders failed")

    await message.answer("Plan created ✅ I’ll remind you before workouts.")

async def schedule_plan_reminders(bot: Bot, chat_id: int, plan: dict) -> None:
    """Schedule workout reminders for the user based on their plan."""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        scheduler.start()
    tzname = plan.get("timezone") or "UTC"
    for day in plan.get("days", []):
        wd = day.get("weekday")
        time_str = day.get("time", "18:00")
        focus = day.get("focus", "Workout")
        for week in range(plan.get("weeks",1)):
            dt = _next_datetime_for(wd, time_str, tzname, weeks_ahead=week)
            remind_at = dt - timedelta(minutes=60)
            if remind_at < datetime.now(tz=remind_at.tzinfo):
                continue
            # Use partial to avoid closure issues with loop variables
            scheduler.add_job(
                partial(bot.send_message, chat_id, f"⏰ {focus} at {time_str}. Ready?"),
                trigger=DateTrigger(run_date=remind_at)
            )

def _next_datetime_for(weekday: str, time_str: str, tzname: str, weeks_ahead: int=0) -> datetime:
    """Compute the next datetime for a given weekday and time in the specified timezone."""
    tz = ZoneInfo(tzname) if tzname else ZoneInfo("UTC")
    now = datetime.now(tz=tz)
    hour, minute = map(int, time_str.split(":",1))
    target_wd = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].index(weekday)
    days_ahead = (target_wd - now.weekday() + 7) % 7 + weeks_ahead*7
    target_date = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target_date

@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    """Handle /today command."""
    await message.answer("Today: 3 sets × 5 reps of a compound lift + accessories. Go crush it! 💪")

@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Handle /stats command."""
    await message.answer("Stats (stub): 5 workouts this week, 12,300 kg total volume.")

@router.message(Command("ask"))
async def cmd_ask(message: Message) -> None:
    """Handle /ask command to answer user questions using OpenAI if available."""
    q = (message.text or "").partition(" ")[2].strip()
    if not q:
        await message.reply("Ask me something like: /ask How to fix my squat form?")
        return
    try:
        # lightweight answer via OpenAI if key exists; otherwise echo
        from .openai_scheduling import SETTINGS as _S  # reuse settings
        import httpx
        if _S.OPENAI_API_KEY:
            headers = {"Authorization": f"Bearer {_S.OPENAI_API_KEY}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role":"user","content": q}]
            }
            async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
                r = await client.post("https://api.openai.com/v1/chat/completions", json=payload)
                r.raise_for_status()
                ans = r.json()["choices"][0]["message"]["content"]
                await message.answer(ans)
        else:
            await message.answer("(No OpenAI key) My quick take: stay consistent, use good form, progressive overload.")
    except Exception as e:
        logging.exception("ask failed")
        await message.answer("Sorry, I had an error answering that.")
        # admin alert happens via logging handler

async def on_startup(bot: Bot) -> None:
    """Startup routine: set up logging, initialize DB, and apply localized commands."""
    setup_logging()
    await repo.init_db()
    await apply_localized_commands(bot)

def main() -> None:
    """Entrypoint for the bot application."""
    if not SETTINGS.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is required")
    bot = Bot(SETTINGS.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)
    # Use lambda to pass bot instance to on_startup
    dp.startup.register(lambda: on_startup(bot))
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    main()
