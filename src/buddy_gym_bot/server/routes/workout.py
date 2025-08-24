"""
Workout tracking API route for BuddyGym.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
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
    is_completed: bool = True  # Default to completed since sets are marked complete when created


@router.post("/workout")
async def log_workout(req: WorkoutRequest) -> dict[str, Any]:
    """Log a workout set."""
    try:
        # Ensure user exists
        user = await repo.upsert_user(req.tg_user_id, handle=None, lang=None)

        # Check if user has an active session (within last 2 hours)
        active_session = await repo.get_active_session(user.id)

        if active_session:
            # Add set to existing session
            set_data = await repo.append_set(
                session_id=active_session.id,
                exercise=req.exercise,
                weight_kg=req.weight_kg,
                input_weight=req.weight_kg,
                input_unit="kg",
                reps=req.reps,
                rpe=req.rpe,
                is_warmup=req.is_warmup,
                is_completed=req.is_completed,
            )
            session_id = active_session.id
        else:
            # Create new workout session
            session = await repo.start_session(user.id, title="Web Log")
            session_id = session.id

            # Log the set with single-unit storage and input tracking
            input_weight = req.weight_kg  # Store what user entered

            set_data = await repo.append_set(
                session_id=session.id,
                exercise=req.exercise,
                weight_kg=req.weight_kg,
                input_weight=input_weight,
                input_unit="kg",  # Default to kg for backward compatibility
                reps=req.reps,
                rpe=req.rpe,
                is_warmup=req.is_warmup,
                is_completed=req.is_completed,
            )

        # Handle referral fulfillment
        await repo.fulfil_referral_for_invitee(req.tg_user_id)

        return {
            "success": True,
            "session_id": session_id,
            "set_id": set_data.id,
            "message": f"Logged {req.exercise}: {req.weight_kg}kg x {req.reps} reps",
        }

    except Exception as e:
        logging.exception("Failed to log workout: %s", e)
        return {"success": False, "error": str(e)}


@router.get("/workout/history")
async def get_workout_history(
    tg_user_id: int = Query(..., description="Telegram user ID"),
) -> dict[str, Any]:
    """Get workout history for a user."""
    try:
        # Ensure user exists
        user = await repo.upsert_user(tg_user_id, handle=None, lang=None)

        # Get workout sessions with sets
        try:
            sessions = await repo.get_user_sessions(user.id)
        except Exception as db_error:
            logging.warning("Database error fetching sessions for user %s: %s", user.id, db_error)
            # Return empty history instead of failing completely
            return {"success": True, "history": []}

        history = []
        for session in sessions:
            try:
                if session.sets:  # Only include sessions with sets
                    # Group sets by exercise
                    exercise_stats = {}
                    for set_row in session.sets:
                        if set_row.exercise not in exercise_stats:
                            exercise_stats[set_row.exercise] = {
                                "sets": 0,
                                "totalReps": 0,
                                "maxWeight": 0,
                            }

                        exercise_stats[set_row.exercise]["sets"] += 1
                        exercise_stats[set_row.exercise]["totalReps"] += set_row.reps
                        exercise_stats[set_row.exercise]["maxWeight"] = max(
                            exercise_stats[set_row.exercise]["maxWeight"], set_row.weight_kg
                        )

                    # Convert to list format
                    exercises = [
                        {
                            "name": exercise,
                            "sets": stats["sets"],
                            "totalReps": stats["totalReps"],
                            "maxWeight": stats["maxWeight"],
                        }
                        for exercise, stats in exercise_stats.items()
                    ]

                    # Calculate duration
                    duration = 0
                    if session.ended_at and session.started_at:
                        duration = int((session.ended_at - session.started_at).total_seconds())

                    history.append(
                        {
                            "id": str(session.id),
                            "date": session.started_at.isoformat(),
                            "duration": duration,
                            "exercises": exercises,
                        }
                    )
            except Exception as session_error:
                # Log individual session errors but continue processing others
                logging.warning(
                    "Error processing session %s: %s",
                    getattr(session, "id", "unknown"),
                    session_error,
                )
                continue

        # Sort by date (newest first)
        history.sort(key=lambda x: x["date"], reverse=True)

        return {"success": True, "history": history}

    except Exception as e:
        logging.exception("Failed to get workout history: %s", e)
        return {"success": False, "error": str(e)}


@router.post("/workout/finish")
async def finish_workout(req: dict) -> dict[str, Any]:
    """Finish a workout session."""
    try:
        # Ensure user exists
        user = await repo.upsert_user(req["tg_user_id"], handle=None, lang=None)

        # Get the active session for this user
        active_session = await repo.get_active_session(user.id)

        if not active_session:
            return {"success": False, "error": "No active workout session found"}

        # Update the session end time
        from datetime import UTC, datetime

        from sqlalchemy import update

        from ...db.models import WorkoutSession

        sessmaker = repo.get_session()
        async with sessmaker() as s:
            await s.execute(
                update(WorkoutSession)
                .where(WorkoutSession.id == active_session.id)
                .values(ended_at=datetime.now(UTC))
            )
            await s.commit()

        return {"success": True, "message": "Workout finished successfully"}

    except Exception as e:
        logging.exception("Failed to finish workout: %s", e)
        return {"success": False, "error": str(e)}
