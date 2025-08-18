"""Test plan rendering functionality."""

from buddy_gym_bot.services.workout_service import WorkoutService


def test_render_plan_message():
    """Test that plan messages are rendered correctly."""
    service = WorkoutService()

    plan = {
        "days": [
            {
                "weekday": "Mon",
                "time": "18:00",
                "focus": "Strength",
                "exercises": [
                    {
                        "name": "Bench Press",
                        "sets": [{"reps": "5"}, {"reps": "5"}, {"reps": "5"}],
                    }
                ],
            }
        ]
    }

    result = service.render_plan_message(plan)
    assert "Mon 18:00 — Strength" in result
    assert "Bench Press: 3x5" in result  # Updated to match new format: count x reps
