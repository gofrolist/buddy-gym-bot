"""
Workout tracking API route for BuddyGym.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ...db import repo
import logging

router = APIRouter()

class TrackSetRequest(BaseModel):
    """
    Request model for tracking a workout set.
    """
    tg_id: int
    exercise: str
    weight_kg: float = Field(ge=0)
    reps: int = Field(ge=1)
    rpe: float | None = Field(default=None)

@router.post("/track/set")
async def track_set(req: TrackSetRequest) -> dict:
    """
    Track a workout set for a user, create a session, and try to fulfill referral.
    """
    # ensure user exists
    user = await repo.upsert_user(req.tg_id, handle=None, lang=None)
    # start a new session (simple approach)
    sess = await repo.start_session(user.id, title="API Log")
    row = await repo.append_set(sess.id, req.exercise, req.weight_kg, req.reps, req.rpe, is_warmup=False)
    # Try fulfil referral on first workout
    try:
        await repo.fulfil_referral_for_invitee(req.tg_id)
    except Exception as e:
        logging.exception("Referral fulfilment failed")
    return {"ok": True, "set_id": row.id}
