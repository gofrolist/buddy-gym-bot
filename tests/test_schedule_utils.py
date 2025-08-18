"""Test schedule utility functions."""

from datetime import datetime
from zoneinfo import ZoneInfo

from buddy_gym_bot.services.reminder_service import ReminderService


def test_next_datetime_for():
    """Test the _next_datetime_for method."""
    service = ReminderService()

    # Test with valid inputs
    result = service._next_datetime_for("Mon", "19:00", "UTC")

    # Ensure result is not None before accessing attributes
    assert result is not None
    assert result.weekday() == 0  # Monday - call the method
    assert result.hour == 19
    assert result.minute == 0

    # Test future date calculation
    now = datetime.now(ZoneInfo("UTC"))
    if result is not None:
        assert result > now

    # Test with invalid weekday
    result = service._next_datetime_for("Invalid", "19:00", "UTC")
    assert result is None
