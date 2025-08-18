"""
Utility functions for command handling.
"""

import logging
from typing import Any

from aiogram.types import Message

from ..config import SETTINGS
from ..db import repo


async def ensure_user_exists(message: Message) -> Any | None:
    """
    Ensure user exists in database and return user data.

    Args:
        message: Telegram message object

    Returns:
        User data dictionary or None if failed
    """
    try:
        if message.from_user is None:
            logging.warning("Message has no from_user")
            return None

        user = await repo.upsert_user(
            message.from_user.id, message.from_user.username, message.from_user.language_code
        )
        return user
    except Exception as e:
        logging.exception("Failed to ensure user exists: %s", e)
        return None


async def handle_referral_click(message: Message) -> bool:
    """
    Handle referral click if present in message.

    Args:
        message: Telegram message object

    Returns:
        True if referral was handled, False otherwise
    """
    if not SETTINGS.FF_REFERRALS:
        return False

    if not message.text or " " not in message.text:
        return False

    if message.from_user is None:
        return False

    payload = message.text.split(" ", 1)[1].strip()
    if not payload.startswith("ref_"):
        return False

    try:
        await repo.record_referral_click(message.from_user.id, payload)
        logging.info("Referral click recorded for user %s", message.from_user.id)
        return True
    except Exception as e:
        logging.exception("Failed to record referral click: %s", e)
        return False


async def handle_referral_fulfillment(user_id: int, message: Message) -> None:
    """Handle referral fulfillment for a user who just logged a workout set."""
    try:
        # Skip if referrals are disabled
        from ..config import SETTINGS

        if not SETTINGS.FF_REFERRALS:
            return

        # Check if referral should be fulfilled (this is the main performance bottleneck)
        fulfilled = await repo.fulfil_referral_for_invitee(user_id)

        if fulfilled:
            # Send success message asynchronously
            try:
                await message.answer(
                    "🎉 Referral bonus activated! You and your friend both got premium days!"
                )
            except Exception as e:
                logging.warning("Failed to send referral success message: %s", e)

    except Exception as e:
        logging.exception("Referral fulfillment failed: %s", e)
        # Don't fail the main command if referral processing fails


def extract_command_args(message: Message, command: str) -> str:
    """
    Extract arguments from a command message.

    Args:
        message: Telegram message object
        command: Command string (e.g., "/track")

    Returns:
        Command arguments as string
    """
    if not message.text:
        return ""

    # Remove command and leading whitespace
    args = message.text[len(command) :].strip()
    return args


def validate_positive_number(value: str, field_name: str) -> tuple[bool, float | None, str]:
    """
    Validate that a string represents a positive number.

    Args:
        value: String value to validate
        field_name: Name of the field for error messages

    Returns:
        Tuple of (is_valid, numeric_value, error_message)
    """
    try:
        num_value = float(value)
        if num_value <= 0:
            return False, None, f"{field_name} must be greater than zero"
        return True, num_value, ""
    except ValueError:
        return False, None, f"{field_name} must be a valid number"
