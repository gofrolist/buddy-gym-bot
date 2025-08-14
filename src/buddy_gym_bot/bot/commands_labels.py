import json
import logging
import os

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")
LANGUAGES = ("en", "ru")


async def apply_localized_commands(bot: Bot) -> None:
    """
    Set localized bot commands for each supported language.
    """
    for lang in LANGUAGES:
        path = os.path.join(LOCALES_DIR, lang, "commands.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            cmds = [BotCommand(command=k, description=v) for k, v in data.items()]
            await bot.set_my_commands(cmds, language_code=lang, scope=BotCommandScopeDefault())
        except Exception as e:
            logging.warning("Failed to set commands for '%s': %s", lang, e)
