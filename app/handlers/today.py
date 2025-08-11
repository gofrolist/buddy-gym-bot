from aiogram import Router
from aiogram.types import Message
from datetime import date
from ..db import get_conn

router = Router()

@router.message(lambda m: m.text and m.text.startswith("/today"))
async def today(msg: Message):
    dow = date.today().isoweekday()
    async with get_conn() as conn:
        cur = await conn.execute(
            "select plan from workouts where tg_user_id=%s and day_of_week=%s and week_start=%s",
            (msg.from_user.id, dow, date.today())
        )
        rec = await cur.fetchone()
    if not rec:
        return await msg.reply("No plan for today. Run /plan first.")
    plan = rec[0]
    lines = [f"• {e['name']}: {e['sets']}×{e['reps']}" for e in plan]
    await msg.reply("📋 *Today*\n" + "\n".join(lines), parse_mode="Markdown")