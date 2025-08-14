import os

from aiogram_i18n import I18n, SimpleI18nMiddleware  # type: ignore

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")
I18N_DOMAIN = "messages"
DEFAULT_LOCALE = "en"


def setup_i18n() -> I18n:
    """
    Set up the I18n instance for aiogram using .po/.mo files.
    """
    return I18n(path=LOCALES_DIR, default_locale=DEFAULT_LOCALE, domain=I18N_DOMAIN)


def i18n_middleware(i18n: I18n) -> SimpleI18nMiddleware:
    """
    Create the aiogram i18n middleware.
    """
    return SimpleI18nMiddleware(i18n)
