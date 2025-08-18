"""
Workout tracking API route for BuddyGym.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...db import repo

router = APIRouter()


class WorkoutRequest(BaseModel):
    tg_user_id: int  # Changed from tg_id to tg_user_id
    exercise: str
    weight_kg: float
    reps: int
    rpe: float | None = None
    is_warmup: bool = False


@router.post("/workout")
async def log_workout(req: WorkoutRequest) -> dict[str, Any]:
    """Log a workout set."""
    try:
        # Ensure user exists
        user = await repo.upsert_user(
            req.tg_user_id, handle=None, lang=None
        )  # Changed from req.tg_id

        # Create workout session
        session = await repo.start_session(user.id, title="Web Log")

        # Log the set
        set_data = await repo.append_set(
            session_id=session.id,
            exercise=req.exercise,
            weight_kg=req.weight_kg,
            reps=req.reps,
            rpe=req.rpe,
            is_warmup=req.is_warmup,
        )

        # Handle referral fulfillment
        await repo.fulfil_referral_for_invitee(req.tg_user_id)  # Changed from req.tg_id

        return {
            "success": True,
            "session_id": session.id,
            "set_id": set_data.id,
            "message": f"Logged {req.exercise}: {req.weight_kg}kg x {req.reps} reps",
        }

    except Exception as e:
        logging.exception("Failed to log workout: %s", e)
        return {"success": False, "error": str(e)}
