"""
BuddyGym FastAPI server main entrypoint.
Handles CORS, static webapp, error handling, and API routers.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..bot.main import on_startup as bot_on_startup
from ..bot.main import router as tg_router
from ..config import SETTINGS
from .routes.exercises import router as r_exercises
from .routes.share import router as r_share
from .routes.workout import router as r_workout

app = FastAPI(title="BuddyGym API")

# CORS setup: allow webapp, Telegram, and web.telegram.org
allowed = set()
try:
    u = urlparse(SETTINGS.WEBAPP_URL)
    origin = f"{u.scheme}://{u.netloc}"
    allowed.add(origin)
except Exception:
    pass
allowed.add("https://t.me")
allowed.add("https://web.telegram.org")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static webapp at /webapp/
static_dir = os.path.join(os.getcwd(), "static", "webapp")
if os.path.isdir(static_dir):
    app.mount("/webapp", StaticFiles(directory=static_dir, html=True), name="webapp")

# Telegram bot setup
bot = Bot(SETTINGS.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(tg_router)

WEBHOOK_PATH = urlparse(SETTINGS.WEBHOOK_URL).path if SETTINGS.WEBHOOK_URL else "/bot"


@app.post(WEBHOOK_PATH)
async def telegram_webhook(update: dict) -> dict:
    tg_update = Update.model_validate(update)
    await dp.feed_update(bot, tg_update)
    return {"ok": True}


@app.on_event("startup")
async def _startup() -> None:
    """FastAPI startup: init bot and database."""
    try:
        await bot_on_startup(bot)
        await dp.emit_startup(bot)
        if SETTINGS.USE_WEBHOOK and SETTINGS.WEBHOOK_URL:
            await bot.set_webhook(SETTINGS.WEBHOOK_URL, drop_pending_updates=True)
    except Exception:
        logging.exception("Startup failed")


@app.on_event("shutdown")
async def _shutdown() -> None:
    """FastAPI shutdown: clean up bot resources."""
    await bot.delete_webhook()
    await dp.emit_shutdown(bot)
    await bot.session.close()


@app.exception_handler(Exception)
async def global_exc_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler: log and return a generic error response.
    """
    logging.exception("Unhandled error")
    return JSONResponse({"ok": False, "error": "internal"}, status_code=500)


@app.get("/healthz")
async def healthz() -> dict:
    """
    Health check endpoint.
    """
    return {"ok": True}


# Routers for API endpoints
app.include_router(r_exercises, prefix="/api/v1")
app.include_router(r_workout, prefix="/api/v1")
app.include_router(r_share, prefix="/api/v1")
