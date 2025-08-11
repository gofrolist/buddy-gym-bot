"""Application entry point and bot setup."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import cast

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from buddy_gym_bot.handlers.ask import router as r_ask
from buddy_gym_bot.handlers.log import router as r_log
from buddy_gym_bot.handlers.plan import router as r_plan
from buddy_gym_bot.handlers.start import router as r_start
from buddy_gym_bot.handlers.stats import router as r_stats
from buddy_gym_bot.handlers.today import router as r_today
from buddy_gym_bot.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    for r in (r_start, r_plan, r_today, r_log, r_stats, r_ask):
        dp.include_router(r)

    if settings.USE_WEBHOOK:
        logger.info("Starting in webhook mode")
        app = web.Application()

        async def healthz(_: web.Request) -> web.Response:
            return web.Response(text="ok")

        app.router.add_get("/healthz", healthz)

        SimpleRequestHandler(dp, bot).register(app, path="/bot")

        async def on_startup(app_: web.Application) -> None:
            await bot.delete_webhook(drop_pending_updates=True)
            if not settings.WEBHOOK_URL:
                raise RuntimeError("WEBHOOK_URL is not set but USE_WEBHOOK=true")
            await bot.set_webhook(settings.WEBHOOK_URL, drop_pending_updates=True)

        # Cast the startup callbacks list, then append — Pyright-safe
        startup_list = cast(
            "list[Callable[[web.Application], Awaitable[None]]]",
            app.on_startup,
        )
        startup_list.append(on_startup)

        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=8080)
    else:
        logger.info("Starting in polling mode")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
