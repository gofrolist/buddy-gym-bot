"""
Workout sharing PNG API route for BuddyGym.
Generates a shareable workout summary image for a user session.
"""

from __future__ import annotations

import io
import logging
from datetime import UTC

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import desc, select

from ...config import SETTINGS
from ...db.models import SetRow, User, WorkoutSession
from ...db.repo import get_session

router = APIRouter()


@router.get("/share/workout.png")
async def share_png(
    uid: int = Query(..., description="Telegram user id"),
    session_id: str = Query(
        "last", pattern=r"^(last|\d+)$", description="Workout session id or 'last'"
    ),
) -> Response:
    """
    Generate a PNG image summarizing a user's workout session.
    """
    if not SETTINGS.FF_SHARE_PNG:
        raise HTTPException(status_code=403, detail="Disabled")
    # Find user & latest session
    sessmaker = get_session()
    try:
        async with sessmaker() as s:
            resu = await s.execute(
                select(User).where(User.tg_user_id == uid)
            )  # Changed from User.tg_id
            user = resu.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="No such user")
            if session_id == "last":
                ress = await s.execute(
                    select(WorkoutSession)
                    .where(WorkoutSession.user_id == user.id)
                    .order_by(desc(WorkoutSession.started_at))
                    .limit(1)
                )
                ws = ress.scalar_one_or_none()
            else:
                try:
                    sid = int(session_id)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail="Invalid session_id") from exc
                ress = await s.execute(
                    select(WorkoutSession).where(
                        WorkoutSession.user_id == user.id, WorkoutSession.id == sid
                    )
                )
                ws = ress.scalar_one_or_none()
            if not ws:
                raise HTTPException(status_code=404, detail="No session")
            ressets = await s.execute(
                select(SetRow).where(SetRow.session_id == ws.id).order_by(SetRow.created_at.asc())
            )
            sets = ressets.scalars().all()
    except Exception as err:
        logging.exception("Failed to fetch user/session/sets for PNG share")
        raise HTTPException(status_code=500, detail="DB error") from err

    # Compute totals
    total_vol = sum((r.weight_kg or 0.0) * (r.reps or 0) for r in sets)
    title = ws.title or "Workout"
    date_str = ws.started_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # Render PNG
    W, H = 900, 500
    img = Image.new("RGB", (W, H), (15, 17, 23))
    draw = ImageDraw.Draw(img)
    # Font
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((30, 30), f"BuddyGym — {title}", font=font_big, fill=(240, 240, 240))
    draw.text(
        (30, 80),
        f"User: @{user.handle or user.tg_user_id}    Date: {date_str}",
        font=font_small,
        fill=(200, 200, 200),
    )
    draw.text((30, 120), f"Total Volume: {total_vol:.0f} kg", font=font_small, fill=(210, 210, 210))
    y = 170
    for r in sets[:8]:
        line = f"• {r.exercise}: {r.weight_kg:g} x {r.reps} " + (
            f"(RPE {r.rpe:g})" if r.rpe else ""
        )
        draw.text((40, y), line, font=font_small, fill=(220, 220, 220))
        y += 36

    buf = io.BytesIO()
    try:
        img.save(buf, format="PNG")
    except Exception as err:
        logging.exception("Failed to render PNG for workout share")
        raise HTTPException(status_code=500, detail="Image error") from err
    return Response(buf.getvalue(), media_type="image/png")
