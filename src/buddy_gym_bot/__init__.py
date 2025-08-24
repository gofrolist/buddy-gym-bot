"""BuddyGym Telegram Bot - AI-powered workout tracking and planning."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("buddy-gym-bot")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
