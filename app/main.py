import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from .settings import settings
from .handlers.start import router as r_start
from .handlers.plan import router as r_plan
from .handlers.today import router as r_today
from .handlers.log import router as r_log
from .handlers.stats import router as r_stats
from .handlers.ask import router as r_ask

async def main():
    bot = Bot(settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    for r in (r_start, r_plan, r_today, r_log, r_stats, r_ask):
        dp.include_router(r)

    if settings.USE_WEBHOOK:
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        app = web.Application()
        SimpleRequestHandler(dp, bot).register(app, path="/bot")
        async def on_startup(app_):
            await bot.set_webhook(settings.WEBHOOK_URL, drop_pending_updates=True)
        app.on_startup.append(on_startup)
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=8080)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())