from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def webapp_button(url: str, text: str) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard with a single button that opens a web app.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))]]
    )
