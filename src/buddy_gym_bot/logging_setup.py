import logging
import traceback

import httpx

from .config import SETTINGS


class TelegramErrorHandler(logging.Handler):
    """
    Logging handler that sends error logs to a Telegram chat via the bot API.
    """

    def emit(self, record: logging.LogRecord) -> None:
        if not SETTINGS.FF_ADMIN_ALERTS:
            return
        if not (SETTINGS.BOT_TOKEN and SETTINGS.ADMIN_CHAT_ID):
            return
        try:
            msg = self.format(record)
            # Compact stack if exists
            if record.exc_info:
                exc_text = "".join(traceback.format_exception(*record.exc_info))
                if len(exc_text) > 3500:
                    exc_text = exc_text[-3500:]
                    exc_text = "[truncated]\n" + exc_text
                msg = f"{msg}\n\n<pre>{exc_text}</pre>"
            url = f"https://api.telegram.org/bot{SETTINGS.BOT_TOKEN}/sendMessage"
            data = {
                "chat_id": SETTINGS.ADMIN_CHAT_ID,
                "text": msg[:3900],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            httpx.post(url, data=data, timeout=5.0)
        except Exception as e:
            logging.getLogger(__name__).error("Failed to send log to Telegram: %s", e)


def setup_logging(level: int = logging.INFO) -> None:
    """
    Set up root logger with stream and Telegram error handlers.
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured
    root.setLevel(level)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)
    tg = TelegramErrorHandler()
    tg.setLevel(logging.ERROR)
    tg.setFormatter(fmt)
    root.addHandler(tg)
