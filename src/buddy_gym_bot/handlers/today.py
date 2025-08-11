"""Handler for the /today command."""

import logging
from datetime import date

from aiogram import Router
from aiogram.types import Message

from ..db import get_conn

router = Router()

logger = logging.getLogger(__name__)


@router.message(lambda m: m.text and m.text.startswith("/today"))
async def today(msg: Message):
    dow = date.today().isoweekday()
    async with get_conn() as conn:
        cur = await conn.execute(
            "select plan from workouts where tg_user_id=%s and day_of_week=%s and week_start=%s",
            (msg.from_user.id, dow, date.today()),
        )
        rec = await cur.fetchone()
    logger.info("Today's workout requested by user %s", getattr(msg.from_user, "id", "unknown"))
    if not rec:
        return await msg.reply("No plan for today. Run /plan first.")
    plan = rec[0]
    lines = [f"• {e['name']}: {e['sets']}x{e['reps']}" for e in plan]
    await msg.reply("📋 *Today*\n" + "\n".join(lines), parse_mode="Markdown")
