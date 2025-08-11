from aiogram import Router, F
from aiogram.types import Message
from ..db import get_conn

router = Router()

@router.message(F.text.startswith("/start"))
async def start(msg: Message):
    async with get_conn() as conn:
        await conn.execute(
          "insert into users (tg_user_id) values (%s) on conflict (tg_user_id) do nothing",
          (msg.from_user.id,)
        )
    await msg.answer(
        "🏋️ Welcome! I’m your gym buddy.\n"
        "• Set up: /plan\n"
        "• Today’s workout: /today\n"
        "• Log a set: /log Bench 3x5 @ 60kg RPE7\n"
        "• Stats: /stats\n"
        "• Ask: /ask How to progress bench?\n\n"
        "_General fitness info only; not medical advice._",
        parse_mode="Markdown"
    )