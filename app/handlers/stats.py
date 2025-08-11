from aiogram import Router
from aiogram.types import Message
from ..db import get_conn

router = Router()

@router.message(lambda m: m.text and m.text.startswith("/stats"))
async def stats(msg: Message):
    async with get_conn() as conn:
        cur = await conn.execute(
          "select exercise, max(weight) from logs where tg_user_id=%s group by exercise order by 2 desc limit 5",
          (msg.from_user.id,)
        )
        rows = await cur.fetchall()
    if not rows:
        return await msg.reply("No stats yet. Log a set with /log")
    lines = [f"• {e}: PR {w:g}" for e,w in rows]
    await msg.reply("📈 *Top PRs*\n" + "\n".join(lines), parse_mode="Markdown")