from aiogram import Router
from aiogram.types import Message
import re
from ..db import get_conn

router = Router()
PAT = re.compile(r"/log\s+(.+?)\s+(\d+)x(\d+)\s*@\s*([\d.]+)\s*(kg|lb)?\s*(?:RPE([\d.]+))?", re.I)

@router.message(lambda m: m.text and m.text.lower().startswith("/log"))
async def log(msg: Message):
    m = PAT.search(msg.text)
    if not m:
        return await msg.reply("Format: /log Bench 3x5 @ 60kg RPE7")
    name, sets, reps, weight, unit, rpe = m.groups()
    async with get_conn() as conn:
        await conn.execute(
          "insert into logs(tg_user_id, exercise, sets, reps, weight, rpe) values (%s,%s,%s,%s,%s,%s)",
          (msg.from_user.id, name.title(), int(sets), int(reps), float(weight), float(rpe or 0))
        )
    await msg.reply("✅ Logged.")