"""
Workout plan API route for BuddyGym.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...db import repo

router = APIRouter()


class PlanResponse(BaseModel):
    success: bool
    plan: dict[str, Any] | None = None
    error: str | None = None


class PlanUpdateRequest(BaseModel):
    tg_user_id: int
    plan: dict[str, Any]


@router.get("/plan/current")
async def get_current_plan(
    tg_user_id: int = Query(..., description="Telegram user ID"),
) -> PlanResponse:
    """Get the current workout plan for a user."""
    try:
        # Ensure user exists
        user = await repo.upsert_user(tg_user_id, handle=None, lang=None)

        # Get user's plan
        plan_data = await repo.get_user_plan(user.id)
        logging.info(f"User {user.id} plan data: {plan_data}")

        if plan_data:
            return PlanResponse(success=True, plan=plan_data)
        else:
            logging.info(f"No plan found for user {user.id}")
        return PlanResponse(success=True, plan=None)

    except Exception as e:
        logging.exception("Failed to get current plan: %s", e)
        return PlanResponse(success=False, error=str(e))


@router.post("/plan/update")
async def update_plan(req: PlanUpdateRequest) -> PlanResponse:
    """Update the workout plan for a user."""
    try:
        # Ensure user exists
        user = await repo.upsert_user(req.tg_user_id, handle=None, lang=None)

        # Update user's plan
        await repo.upsert_user_plan(user.id, req.plan)
        logging.info(f"Updated plan for user {user.id}")

        return PlanResponse(success=True, plan=req.plan)

    except Exception as e:
        logging.exception("Failed to update plan: %s", e)
        return PlanResponse(success=False, error=str(e))
