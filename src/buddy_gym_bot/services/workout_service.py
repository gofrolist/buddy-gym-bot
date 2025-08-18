"""
Service for workout plan creation and management.
"""

import logging
from typing import Any

from ..bot.openai_scheduling import generate_schedule
from ..db import repo
from ..exercisedb import ExerciseDBClient


class WorkoutService:
    """Service for handling workout-related operations."""

    async def create_workout_plan(
        self, user_id: int, request_text: str, timezone: str
    ) -> dict[str, Any]:
        """Create a workout plan using OpenAI."""
        try:
            # Get existing plan if available
            existing_plan = None
            try:
                existing_plan = await repo.get_user_plan(user_id)
            except Exception:
                logging.debug("No existing plan found for user %s", user_id)

            # Generate workout plan (pass existing plan for context)
            plan = await generate_schedule(request_text, timezone, existing_plan)
            if not plan:
                return {"error": "Failed to generate workout plan"}

            # Enrich with ExerciseDB data
            exercisedb = ExerciseDBClient()
            try:
                enriched_plan = await exercisedb.map_plan_exercises(plan)
            finally:
                await exercisedb.close()

            # Save to database
            await repo.upsert_user_plan(user_id, enriched_plan)

            return enriched_plan

        except Exception as e:
            logging.exception("Failed to create workout plan: %s", e)
            return {"error": f"Failed to create workout plan: {e!s}"}

    async def log_workout_set(
        self,
        user_id: int,
        exercise: str,
        weight: float,
        reps: int,
        rpe: float | None = None,
        is_warmup: bool = False,
    ) -> dict[str, Any]:
        """Log a workout set - optimized for speed."""
        try:
            # Use optimized single-transaction method for better performance
            from ..db import repo

            session, set_data = await repo.start_session_and_append_set(
                user_id=user_id,
                exercise=exercise,
                weight_kg=weight,
                reps=reps,
                rpe=rpe,
                is_warmup=is_warmup,
                title="Quick Log",
            )

            return {
                "session_id": session.id,
                "set_id": set_data.id,
                "exercise": exercise,
                "weight": weight,
                "reps": reps,
                "rpe": rpe,
                "is_warmup": is_warmup,
            }

        except Exception as e:
            logging.exception("Failed to log workout set: %s", e)
            return {"error": f"Failed to log workout set: {e!s}"}

    def render_plan_message(self, plan: dict[str, Any]) -> str:
        """Render a workout plan as a formatted message."""
        if "error" in plan:
            return f"❌ Error: {plan['error']}"

        try:
            message = "Plan created ✅ I'll remind you before workouts.\n\n"

            if "days" in plan:
                days: list[dict[str, Any]] = plan["days"]
                for day in days:
                    # Extract day info
                    weekday = day.get("weekday", "Unknown Day")
                    time = day.get("time", "")
                    focus = day.get("focus", "")
                    duration = day.get("duration", "")

                    # Build day header
                    header = weekday
                    if time:
                        header += f" {time}"
                    if focus:
                        header += f" — {focus}"
                    if duration:
                        header += f" — {duration}"

                    message += f"**{header}**\n"

                    # Process exercises
                    exercises: list[dict[str, Any]] = day.get("exercises", [])
                    for exercise in exercises:
                        name = exercise.get("name", "Unknown Exercise")

                        # Handle different set formats
                        sets_data: list[dict[str, Any]] = exercise.get("sets", [])
                        if isinstance(sets_data, list) and sets_data:
                            # Count sets
                            num_sets = len(sets_data)

                            # Extract reps from first set
                            first_set: dict[str, Any] = sets_data[0]
                            if isinstance(first_set, dict):
                                reps = first_set.get("reps", "?")
                                message += f"• {name}: {num_sets}x{reps}\n"
                            else:
                                message += f"• {name}: {num_sets} sets\n"
                        else:
                            # Fallback for simple format
                            sets = exercise.get("sets", "?")
                            reps = exercise.get("reps", "?")
                            message += f"• {name}: {sets}x{reps}\n"

                    message += "\n"

            return message.strip()

        except Exception as e:
            logging.exception("Failed to render plan message: %s", e)
            return "❌ Error rendering workout plan"
