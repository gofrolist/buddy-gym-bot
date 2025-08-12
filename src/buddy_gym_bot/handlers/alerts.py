"""Utilities for sending admin-facing alerts."""

from __future__ import annotations

import logging

from aiogram import Bot

from buddy_gym_bot.settings import settings

logger = logging.getLogger(__name__)


async def alert_admin(bot: Bot, text: str) -> None:
    """Send an alert to the configured admin chat or log it."""
    admin_chat_id = settings.ADMIN_CHAT_ID
    if not admin_chat_id:
        logger.error("ADMIN_ALERT: %s", text)
        return
    try:
        await bot.send_message(admin_chat_id, text)
    except Exception as exc:  # pragma: no cover - best effort
        logger.exception("Failed to send admin alert: %s", exc)
