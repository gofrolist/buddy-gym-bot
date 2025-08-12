"""Handler for the /plan command."""

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.types import Message
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from ..db import get_conn
from ..planner import UserProfile, make_week_plan

router = Router()

logger = logging.getLogger(__name__)


@router.message(F.text.startswith("/plan"))
async def plan(msg: Message):
    parts = msg.text.split()
    goal = parts[1] if len(parts) > 1 else "general"
    days = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 3
    equip = parts[3] if len(parts) > 3 else "gym"
    profile = UserProfile(goal=goal, experience="novice", days_per_week=days, equipment=equip)
    week = make_week_plan(profile)
    logger.info(
        "Generated plan for user %s: goal=%s days=%s equip=%s",
        getattr(msg.from_user, "id", "unknown"),
        goal,
        days,
        equip,
    )

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    async with get_conn() as conn:
        await conn.execute(
            "delete from workouts where tg_user_id=%s and week_start=%s",
            (msg.from_user.id, week_start),
        )
        is_psycopg = isinstance(conn, AsyncConnection)
        for idx, _day in enumerate(week, start=1):
            plan_payload = Jsonb(week[idx - 1]) if is_psycopg else week[idx - 1]
            await conn.execute(
                "insert into workouts (tg_user_id, day_of_week, plan, week_start) values (%s,%s,%s,%s)",
                (msg.from_user.id, idx, plan_payload, week_start),
            )
    await msg.reply(f"✅ Plan created for {days} days/week ({goal}, {equip}). Use /today.")
