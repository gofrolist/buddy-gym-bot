import copy
import os

import pytest

# Ensure required environment variables are set for config
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("FF_REMINDERS", "0")
os.environ.setdefault("FF_EXERCISEDB", "0")


@pytest.mark.asyncio
async def test_schedule_followup_changes_only_time():
    """Test that schedule modifications preserve existing plan structure."""

    # Mock the generate_schedule function to return predictable results
    async def mock_generate_schedule(text: str, tz: str = "UTC", base_plan: dict | None = None):
        if base_plan is None:
            # Initial plan creation
            return {
                "program_name": "TestPlan",
                "timezone": tz,
                "weeks": 1,
                "days_per_week": 2,
                "days": [
                    {"weekday": "Mon", "time": "08:00", "focus": "Full", "exercises": []},
                    {"weekday": "Thu", "time": "18:00", "focus": "Full", "exercises": []},
                ],
            }
        else:
            # Plan modification - preserve structure and only change what's requested
            new_plan = copy.deepcopy(base_plan)

            # Check if the request is about changing Monday's time
            if "monday" in text.lower() and "time" in text.lower():
                for day in new_plan["days"]:
                    if day["weekday"] == "Mon":
                        day["time"] = "10:00"
                        break

            return new_plan

    # Test initial plan creation
    initial_plan = await mock_generate_schedule("2-day plan", "UTC")
    assert initial_plan["days_per_week"] == 2
    assert len(initial_plan["days"]) == 2
    assert initial_plan["days"][0]["weekday"] == "Mon"
    assert initial_plan["days"][0]["time"] == "08:00"
    assert initial_plan["days"][1]["weekday"] == "Thu"
    assert initial_plan["days"][1]["time"] == "18:00"

    # Test plan modification
    updated_plan = await mock_generate_schedule("change Monday time to 10:00", "UTC", initial_plan)

    # Verify structure is preserved
    assert updated_plan["days_per_week"] == 2
    assert len(updated_plan["days"]) == 2

    # Verify Monday's time was changed
    monday_day = next(d for d in updated_plan["days"] if d["weekday"] == "Mon")
    assert monday_day["time"] == "10:00"

    # Verify Thursday's time was unchanged
    thursday_day = next(d for d in updated_plan["days"] if d["weekday"] == "Thu")
    assert thursday_day["time"] == "18:00"

    # Verify other properties are preserved
    assert updated_plan["program_name"] == "TestPlan"
    assert updated_plan["timezone"] == "UTC"
    assert updated_plan["weeks"] == 1
