# src/buddy_gym_bot/handlers/log.py
from __future__ import annotations

import re

from aiogram import Router
from aiogram.types import Message

from buddy_gym_bot.db import get_conn

router = Router()

# /log Bench 3x5 @ 60kg RPE7
PAT = re.compile(
    r"/log\s+(.+?)\s+(\d+)x(\d+)\s*@\s*([\d.]+)\s*(kg|lb)?\s*(?:RPE([\d.]+))?",
    re.IGNORECASE,
)


@router.message(lambda m: (m.text or "").lower().startswith("/log"))
async def log(msg: Message) -> None:
    # Guard possibly-None text for type checker
    text: str = msg.text or ""
    m = PAT.search(text)
    if not m:
        await msg.reply("Format: /log Bench 3x5 @ 60kg RPE7")
        return

    # Guard from_user; channel posts etc. may not have it
    if not msg.from_user:
        return
    uid = msg.from_user.id

    name, sets_s, reps_s, weight_s, unit, rpe_s = m.groups()

    # Parse numbers with safe fallbacks
    try:
        sets_i = int(sets_s)
        reps_i = int(reps_s)
        weight_f = float(weight_s)
        rpe_f = float(rpe_s) if rpe_s is not None else 0.0
    except (TypeError, ValueError):
        await msg.reply("Couldn't parse numbers. Try: /log Bench 3x5 @ 60kg RPE7")
        return

    exercise = (name or "").title()
    unit_disp = unit or ""

    async with get_conn() as conn:
        await conn.execute(
            "insert into logs (tg_user_id, exercise, sets, reps, weight, rpe) "
            "values (%s, %s, %s, %s, %s, %s)",
            (uid, exercise, sets_i, reps_i, weight_f, rpe_f),
        )

    await msg.reply(
        f"✅ Logged: {exercise} {sets_i}x{reps_i} @ {weight_f:g}{unit_disp} RPE{rpe_f:g}"
    )
