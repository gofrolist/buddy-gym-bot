from aiogram import Router, F
from aiogram.types import Message
from datetime import date
from ..db import get_conn
from ..planner import UserProfile, make_week_plan

router = Router()

@router.message(F.text.startswith("/plan"))
async def plan(msg: Message):
    parts = msg.text.split()
    goal = parts[1] if len(parts)>1 else "general"
    days = int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 3
    equip = parts[3] if len(parts)>3 else "gym"
    profile = UserProfile(goal=goal, experience="novice", days_per_week=days, equipment=equip)
    week = make_week_plan(profile)

    async with get_conn() as conn:
        await conn.execute("delete from workouts where tg_user_id=%s and week_start=%s",
                           (msg.from_user.id, date.today()))
        for idx, day in enumerate(week, start=1):
            await conn.execute(
                "insert into workouts (tg_user_id, day_of_week, plan, week_start) values (%s,%s,%s,%s)",
                (msg.from_user.id, idx, week[idx-1], date.today())
            )
    await msg.reply(f"✅ Plan created for {days} days/week ({goal}, {equip}). Use /today.")