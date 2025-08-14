from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def webapp_button(url: str, text: str) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard with a single button that opens a web app.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))]]
    )


def wave_hello(name: str) -> str:
    """Return a friendly greeting with a wave emoji."""
    return f"👋 Hello, {name}!"
