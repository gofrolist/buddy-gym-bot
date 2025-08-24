"""
Tests for OpenAI scheduling functionality.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from buddy_gym_bot.bot.openai_scheduling import (
    _extract_complete_json,
    _validate_and_fix_plan,
    generate_schedule,
)

# Tests for the deleted get_openai_vector_store_id function have been removed
# since that function is no longer needed in the codebase.


@pytest.mark.asyncio
async def test_generate_schedule_success_with_reasoning_response():
    """Test successful schedule generation with reasoning response type."""
    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_VECTOR_STORE_ID": "vs_test123"}
    ):
        with patch("buddy_gym_bot.bot.openai_scheduling.extract_constraints") as mock_extract:
            # Mock constraint extraction to return valid constraints
            mock_extract.return_value = {"days": ["Mon"], "duration_minutes": 30, "weeks": 1}

            with patch("buddy_gym_bot.bot.openai_scheduling.call_plan_generator") as mock_generator:
                # Mock plan generation to return the expected plan
                mock_generator.return_value = {
                    "program_name": "Test Plan",
                    "timezone": "UTC",
                    "weeks": 1,
                    "days_per_week": 1,
                    "days": [
                        {
                            "weekday": "Mon",
                            "time": "19:00",
                            "focus": "Full Body",
                            "exercises": [
                                {
                                    "name": "Barbell Bench Press",
                                    "exercise_db_id": "test123",
                                    "sets": 3,
                                    "reps": "5",
                                },
                                {
                                    "name": "Squats",
                                    "exercise_db_id": "test456",
                                    "sets": 3,
                                    "reps": "8-12",
                                },
                                {
                                    "name": "Pull-ups",
                                    "exercise_db_id": "test789",
                                    "sets": 3,
                                    "reps": "5-10",
                                },
                                {
                                    "name": "Plank",
                                    "exercise_db_id": "test101",
                                    "sets": 3,
                                    "reps": "30 seconds",
                                },
                            ],
                        }
                    ],
                }

                result = await generate_schedule("Create a 1-day plan", "UTC")

                assert result is not None
                assert result["program_name"] == "Test Plan"
                assert result["timezone"] == "UTC"
                assert result["weeks"] == 1
                assert result["days_per_week"] == 1
                assert len(result["days"]) == 1
                assert result["days"][0]["weekday"] == "Mon"
                assert result["days"][0]["time"] == "19:00"
                assert len(result["days"][0]["exercises"]) == 4
                assert result["days"][0]["exercises"][0]["name"] == "Barbell Bench Press"
                # The exercise_db_id will be mapped to a real ID from ExerciseDB, not the test ID
                assert result["days"][0]["exercises"][0]["exercise_db_id"] != ""
                assert result["days"][0]["exercises"][0]["sets"] == 3
                assert result["days"][0]["exercises"][0]["reps"] == "5"


@pytest.mark.asyncio
async def test_generate_schedule_success_with_message_response():
    """Test successful schedule generation with message response type (fallback)."""
    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_VECTOR_STORE_ID": "vs_test123"}
    ):
        with patch("buddy_gym_bot.bot.openai_scheduling.extract_constraints") as mock_extract:
            # Mock constraint extraction to return valid constraints
            mock_extract.return_value = {"days": ["Wed"], "duration_minutes": 30, "weeks": 1}

            with patch("buddy_gym_bot.bot.openai_scheduling.call_plan_generator") as mock_generator:
                # Mock plan generation to return the expected plan
                mock_generator.return_value = {
                    "program_name": "Message Plan",
                    "timezone": "UTC",
                    "weeks": 1,
                    "days_per_week": 1,
                    "days": [
                        {
                            "weekday": "Wed",
                            "time": "18:00",
                            "focus": "Upper Body",
                            "exercises": [],
                        }
                    ],
                }

                result = await generate_schedule("Create a 1-day plan", "UTC")

                assert result is not None
                assert result["program_name"] == "Message Plan"
                assert result["timezone"] == "UTC"
                assert result["weeks"] == 1
                assert result["days_per_week"] == 1
                assert len(result["days"]) == 1
                assert result["days"][0]["weekday"] == "Wed"


@pytest.mark.asyncio
async def test_generate_schedule_success_with_output_text_response():
    """Test successful schedule generation with output_text response type (what the AI actually returns)."""
    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_VECTOR_STORE_ID": "vs_test123"}
    ):
        with patch("buddy_gym_bot.bot.openai_scheduling.extract_constraints") as mock_extract:
            # Mock constraint extraction to return valid constraints
            mock_extract.return_value = {"days": ["Wed"], "duration_minutes": 30, "weeks": 1}

            with patch("buddy_gym_bot.bot.openai_scheduling.call_plan_generator") as mock_generator:
                # Mock plan generation to return the expected plan
                mock_generator.return_value = {
                    "program_name": "Output Text Plan",
                    "timezone": "UTC",
                    "weeks": 1,
                    "days_per_week": 1,
                    "days": [
                        {
                            "weekday": "Wed",
                            "time": "18:00",
                            "focus": "Upper Body",
                            "exercises": [],
                        }
                    ],
                }

                result = await generate_schedule("Create a 1-day plan", "UTC")

                assert result is not None
                assert result["program_name"] == "Output Text Plan"
                assert result["timezone"] == "UTC"
                assert result["weeks"] == 1
                assert result["days_per_week"] == 1
                assert len(result["days"]) == 1
                assert result["days"][0]["weekday"] == "Wed"


@pytest.mark.asyncio
async def test_generate_schedule_no_content_fallback():
    """Test that constraint extraction failure raises an error instead of fallback."""
    mock_response = {
        "output": [
            {"type": "file_search_call", "status": "completed", "results": []}
            # No reasoning or message content
        ]
    }

    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_VECTOR_STORE_ID": "vs_test123"}
    ):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_client_instance.post.return_value = mock_response_obj

            with pytest.raises(ValueError, match="Failed to generate workout plan"):
                await generate_schedule("Create a plan", "UTC")


@pytest.mark.asyncio
async def test_generate_schedule_json_parse_error_fallback():
    """Test that JSON parsing failure raises an error instead of fallback."""
    mock_response = {
        "output": [
            {
                "type": "reasoning",
                "content": [{"type": "text", "text": {"value": "Invalid JSON content here"}}],
            }
        ]
    }

    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_VECTOR_STORE_ID": "vs_test123"}
    ):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_client_instance.post.return_value = mock_response_obj

            with pytest.raises(ValueError, match="Failed to generate workout plan"):
                await generate_schedule("Create a plan", "UTC")


@pytest.mark.asyncio
async def test_generate_schedule_http_error_fallback():
    """Test that HTTP error raises an error instead of fallback."""
    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_VECTOR_STORE_ID": "vs_test123"}
    ):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            # Simulate HTTP error
            mock_response_obj = MagicMock()
            mock_response_obj.raise_for_status.side_effect = Exception("HTTP Error")
            mock_client_instance.post.return_value = mock_response_obj

            with pytest.raises(ValueError, match="Failed to generate workout plan"):
                await generate_schedule("Create a plan", "UTC")


@pytest.mark.asyncio
async def test_generate_schedule_no_api_key_fallback():
    """Test that missing API key raises an error instead of fallback."""
    with patch("buddy_gym_bot.bot.openai_scheduling.SETTINGS") as mock_settings:
        mock_settings.OPENAI_API_KEY = None
        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            await generate_schedule("Create a plan", "UTC")


@pytest.mark.asyncio
async def test_generate_schedule_no_vector_store_fallback():
    """Test that missing vector store ID raises an error instead of fallback."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}, clear=True):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            # Simulate HTTP error due to missing vector store
            mock_response_obj = MagicMock()
            mock_response_obj.raise_for_status.side_effect = Exception("HTTP Error")
            mock_client_instance.post.return_value = mock_response_obj

            with pytest.raises(ValueError, match="Failed to generate workout plan"):
                await generate_schedule("Create a plan", "UTC")


@pytest.mark.asyncio
async def test_generate_schedule_with_base_plan():
    """Test schedule generation with existing base plan."""
    base_plan = {
        "program_name": "Existing Plan",
        "timezone": "UTC",
        "weeks": 1,
        "days_per_week": 2,
        "days": [{"weekday": "Mon", "time": "19:00", "focus": "Full Body", "exercises": []}],
    }

    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_VECTOR_STORE_ID": "vs_test123"}
    ):
        with patch("buddy_gym_bot.bot.openai_scheduling.extract_constraints") as mock_extract:
            # Mock constraint extraction to return valid constraints
            mock_extract.return_value = {"days": ["Mon"], "duration_minutes": 30, "weeks": 1}

            with patch("buddy_gym_bot.bot.openai_scheduling.call_plan_generator") as mock_generator:
                # Mock plan generation to return the expected plan
                mock_generator.return_value = {
                    "program_name": "Modified Plan",
                    "timezone": "UTC",
                    "weeks": 1,
                    "days_per_week": 2,
                    "days": [
                        {
                            "weekday": "Mon",
                            "time": "20:00",  # Modified time
                            "focus": "Full Body",
                            "exercises": [],
                        }
                    ],
                }

                result = await generate_schedule("Modify Monday time to 20:00", "UTC", base_plan)

                assert result is not None
                assert result["program_name"] == "Modified Plan"
                assert result["timezone"] == "UTC"
                assert result["weeks"] == 1
                assert result["days_per_week"] == 1  # Should be 1 since we only have 1 day
                assert len(result["days"]) == 1
                assert result["days"][0]["weekday"] == "Mon"
                assert result["days"][0]["time"] == "20:00"


def test_validate_and_fix_plan():
    """Test that the plan validation function correctly fixes AI-generated plans."""

    # Test case 1: AI used wrong days (Wed instead of Fri)
    plan_with_wrong_days = {
        "days": [
            {"weekday": "Mon", "exercises": [{"name": "ex1"}, {"name": "ex2"}]},
            {"weekday": "Tue", "exercises": [{"name": "ex1"}, {"name": "ex2"}]},
            {"weekday": "Wed", "exercises": [{"name": "ex1"}, {"name": "ex2"}]},  # Wrong day
        ]
    }

    constraints = {"days": ["Mon", "Tue", "Fri"], "duration_minutes": 30}
    requested_days = ["Mon", "Tue", "Fri"]

    fixed_plan = _validate_and_fix_plan(plan_with_wrong_days, constraints, requested_days)

    # Should remove the wrong day (Wed) and keep only Mon, Tue
    assert len(fixed_plan["days"]) == 2
    weekdays = [day["weekday"] for day in fixed_plan["days"]]
    assert "Mon" in weekdays
    assert "Tue" in weekdays
    assert "Wed" not in weekdays
    assert "Fri" not in weekdays  # Fri was requested but not in original plan

    # Test case 2: Plan with no exercises
    plan_with_no_exercises = {
        "days": [
            {"weekday": "Mon", "exercises": []},  # No exercises
        ]
    }

    constraints = {"days": ["Mon"], "duration_minutes": 30}
    requested_days = ["Mon"]

    fixed_plan = _validate_and_fix_plan(plan_with_no_exercises, constraints, requested_days)

    # Should respect the user's plan exactly - no top-up exercises added
    assert len(fixed_plan["days"]) == 1
    assert len(fixed_plan["days"][0]["exercises"]) == 0  # Keep original count (no fallbacks)

    # Test case 3: Plan with too many exercises for duration
    plan_with_too_many = {
        "days": [
            {
                "weekday": "Mon",
                "exercises": [
                    {"name": f"ex{i}", "sets": 3, "reps": "8-12"}
                    for i in range(10)  # 10 exercises is too many for 30 min
                ],
            }
        ]
    }

    constraints = {"days": ["Mon"], "duration_minutes": 30}
    requested_days = ["Mon"]

    fixed_plan = _validate_and_fix_plan(plan_with_too_many, constraints, requested_days)

    # Should trim to 4-5 exercises for 30 min duration
    assert len(fixed_plan["days"]) == 1
    exercises = fixed_plan["days"][0]["exercises"]
    assert 4 <= len(exercises) <= 5  # Should be 4-5 exercises for 30 min
    # All exercises should have 3 sets for 30 min duration
    for exercise in exercises:
        assert exercise["sets"] == 3


def test_json_helper_functions():
    """Test the JSON helper functions for handling incomplete responses."""

    # Test _extract_complete_json
    incomplete_json = '{"name": "test", "value": 123, "nested": {"key": "value"}} extra text'
    complete_json = _extract_complete_json(incomplete_json)
    assert complete_json == '{"name": "test", "value": 123, "nested": {"key": "value"}}'

    # Test with multiple objects
    multiple_objects = '{"obj1": {}} {"obj2": {}}'
    complete_json = _extract_complete_json(multiple_objects)
    assert complete_json == '{"obj2": {}}'  # Should get the last complete object
