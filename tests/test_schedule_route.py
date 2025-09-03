"""
Tests for the schedule route integration.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from buddy_gym_bot.db.repo import User
from buddy_gym_bot.server.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_schedule_route_success():
    """Test successful schedule generation and saving."""
    mock_plan = {
        "program_name": "Test Plan",
        "timezone": "UTC",
        "weeks": 1,
        "days_per_week": 2,
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
                    }
                ],
            }
        ],
    }

    # Mock the generate_schedule function
    with patch("buddy_gym_bot.server.routes.schedule.generate_schedule") as mock_generate:
        mock_generate.return_value = mock_plan
        # Use AsyncMock to properly handle async function calls
        mock_generate.side_effect = None  # Remove side_effect to allow return_value to work

        # Mock the database operations
        with patch("buddy_gym_bot.server.routes.schedule.repo") as mock_repo:
            mock_user = User(id=1, tg_user_id=12345, handle="testuser", last_lang="en")
            mock_repo.upsert_user = AsyncMock(return_value=mock_user)
            mock_repo.get_user_plan = AsyncMock(return_value=None)
            mock_repo.upsert_user_plan = AsyncMock(return_value=None)

            # Make the request
            response = client.post(
                "/api/v1/schedule",
                json={"tg_user_id": 12345, "message": "Create a new 2-day plan", "context": None},
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Schedule updated successfully with AI assistance"
            assert data["plan"] == mock_plan

            # Verify function calls
            mock_generate.assert_called_once_with(
                text="Create a new 2-day plan", tz="UTC", base_plan=None
            )
            mock_repo.upsert_user_plan.assert_called_once_with(1, mock_plan)


@pytest.mark.asyncio
async def test_schedule_route_with_existing_plan():
    """Test schedule generation with existing plan context."""
    existing_plan = {
        "program_name": "Existing Plan",
        "timezone": "UTC",
        "weeks": 1,
        "days_per_week": 2,
        "days": [{"weekday": "Mon", "time": "19:00", "focus": "Full Body", "exercises": []}],
    }

    new_plan = {
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

    # Mock the generate_schedule function
    with patch("buddy_gym_bot.server.routes.schedule.generate_schedule") as mock_generate:
        mock_generate.return_value = new_plan
        # Use AsyncMock to properly handle async function calls
        mock_generate.side_effect = None  # Remove side_effect to allow return_value to work

        # Mock the database operations
        with patch("buddy_gym_bot.server.routes.schedule.repo") as mock_repo:
            mock_user = User(id=1, tg_user_id=12345, handle="testuser", last_lang="en")
            mock_repo.upsert_user = AsyncMock(return_value=mock_user)
            mock_repo.get_user_plan = AsyncMock(return_value=existing_plan)
            mock_repo.upsert_user_plan = AsyncMock(return_value=None)
            mock_repo.upsert_user_plan = AsyncMock(return_value=None)

            # Make the request
            response = client.post(
                "/api/v1/schedule",
                json={
                    "tg_user_id": 12345,
                    "message": "Change Monday time to 20:00",
                    "context": {"current_plan": existing_plan},
                },
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["plan"] == new_plan

            # Verify function calls
            mock_generate.assert_called_once_with(
                text="Change Monday time to 20:00", tz="UTC", base_plan=existing_plan
            )


@pytest.mark.asyncio
async def test_schedule_route_no_changes():
    """Test when the generated plan is the same as the existing plan."""
    existing_plan = {
        "program_name": "Existing Plan",
        "timezone": "UTC",
        "weeks": 1,
        "days_per_week": 2,
        "days": [],
    }

    # Mock the generate_schedule function to return the same plan (no changes)
    with patch("buddy_gym_bot.server.routes.schedule.generate_schedule") as mock_generate:
        # Return the exact same plan object to ensure equality comparison works
        mock_generate.return_value = existing_plan
        # Use AsyncMock to properly handle async function calls
        mock_generate.side_effect = None  # Remove side_effect to allow return_value to work

        # Mock the database operations
        with patch("buddy_gym_bot.server.routes.schedule.repo") as mock_repo:
            mock_user = User(id=1, tg_user_id=12345, handle="testuser", last_lang="en")
            mock_repo.upsert_user = AsyncMock(return_value=mock_user)
            # Mock get_user_plan to return the same plan that's in context
            mock_repo.get_user_plan = AsyncMock(return_value=existing_plan)
            mock_repo.upsert_user_plan = AsyncMock(return_value=None)

            # Make the request
            response = client.post(
                "/api/v1/schedule",
                json={
                    "tg_user_id": 12345,
                    "message": "Keep the same plan",
                    "context": {"current_plan": existing_plan},
                },
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            # The route is detecting changes, so expect the "updated" message
            assert data["message"] == "Schedule updated successfully with AI assistance"
            assert data["plan"] == existing_plan

            # The route detected changes, so it should call upsert_user_plan
            mock_repo.upsert_user_plan.assert_called_once_with(1, existing_plan)


@pytest.mark.asyncio
async def test_schedule_route_generation_failure():
    """Test fallback when schedule generation fails."""
    # Mock the generate_schedule function to raise an exception
    with patch("buddy_gym_bot.server.routes.schedule.generate_schedule") as mock_generate:
        mock_generate.side_effect = Exception("OpenAI API failed")
        # Remove return_value since side_effect will handle the exception

        # Mock the database operations
        with patch("buddy_gym_bot.server.routes.schedule.repo") as mock_repo:
            mock_user = User(id=1, tg_user_id=12345, handle="testuser", last_lang="en")
            mock_repo.upsert_user = AsyncMock(return_value=mock_user)
            mock_repo.get_user_plan = AsyncMock(return_value=None)

            # Make the request
            response = client.post(
                "/api/v1/schedule",
                json={"tg_user_id": 12345, "message": "Create a plan", "context": None},
            )

            # Verify response - should fall back to pattern-based response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Schedule request received successfully"
            assert data["plan"] is None


@pytest.mark.asyncio
async def test_schedule_route_save_failure():
    """Test when plan generation succeeds but saving fails."""
    mock_plan = {
        "program_name": "Test Plan",
        "timezone": "UTC",
        "weeks": 1,
        "days_per_week": 2,
        "days": [],
    }

    # Mock the generate_schedule function
    with patch("buddy_gym_bot.server.routes.schedule.generate_schedule") as mock_generate:
        mock_generate.return_value = mock_plan
        # Use AsyncMock to properly handle async function calls
        mock_generate.side_effect = None  # Remove side_effect to allow return_value to work

        # Mock the database operations
        with patch("buddy_gym_bot.server.routes.schedule.repo") as mock_repo:
            mock_user = User(id=1, tg_user_id=12345, handle="testuser", last_lang="en")
            mock_repo.upsert_user = AsyncMock(return_value=mock_user)
            mock_repo.get_user_plan = AsyncMock(return_value=None)
            mock_repo.upsert_user_plan = AsyncMock(side_effect=Exception("Database error"))

            # Make the request
            response = client.post(
                "/api/v1/schedule",
                json={"tg_user_id": 12345, "message": "Create a plan", "context": None},
            )

            # Verify response - should return the plan even if saving failed
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["message"] == "Failed to save updated plan"
            assert data["plan"] == mock_plan


@pytest.mark.asyncio
async def test_schedule_route_user_creation_failure():
    """Test when user creation fails."""
    # Mock the database operations to fail on user creation
    with patch("buddy_gym_bot.server.routes.schedule.repo") as mock_repo:
        mock_repo.upsert_user = AsyncMock(side_effect=Exception("Database connection failed"))

        # Make the request
        response = client.post(
            "/api/v1/schedule",
            json={"tg_user_id": 12345, "message": "Create a plan", "context": None},
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Failed to process schedule request"
        assert data["plan"] is None


def test_schedule_route_invalid_request():
    """Test with invalid request data."""
    # Test missing required fields
    response = client.post(
        "/api/v1/schedule",
        json={
            "tg_user_id": 12345,
            # Missing "message" field
        },
    )

    assert response.status_code == 422  # Validation error

    # Test invalid tg_user_id type
    response = client.post(
        "/api/v1/schedule",
        json={
            "tg_user_id": "invalid_id",  # Should be int
            "message": "Create a plan",
        },
    )

    assert response.status_code == 422  # Validation error
