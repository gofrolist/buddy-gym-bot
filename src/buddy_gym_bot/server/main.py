"""
BuddyGym FastAPI server main entrypoint.
Handles CORS, static webapp, error handling, and API routers.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.parse import urlparse

import psutil
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ..bot.main import on_shutdown as bot_on_shutdown
from ..bot.main import on_startup as bot_on_startup
from ..bot.main import router as tg_router
from ..config import SETTINGS
from ..db import close_db, init_db
from .routes.exercises import router as r_exercises
from .routes.plan import router as r_plan
from .routes.schedule import router as r_schedule
from .routes.share import router as r_share
from .routes.workout import router as r_workout


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global bot, dp
    try:
        # Initialize database
        await init_db()
        logging.info("Database initialized")

        # Skip bot initialization for local development with test token
        if SETTINGS.BOT_TOKEN == "test-token":
            logging.info("Skipping bot initialization for local development")
            bot = None
            dp = None
        else:
            # Initialize bot and dispatcher
            bot = Bot(SETTINGS.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            dp.include_router(tg_router)

            await bot_on_startup(bot)
            await dp.emit_startup(bot)
            if SETTINGS.USE_WEBHOOK and SETTINGS.WEBHOOK_URL:
                await bot.set_webhook(SETTINGS.WEBHOOK_URL, drop_pending_updates=True)
                logging.info("Webhook set to %s", SETTINGS.WEBHOOK_URL)

            # Update bot health status
            try:
                from ..bot.main import update_health_status

                update_health_status("healthy")
            except Exception:
                pass

        logging.info("FastAPI server startup completed")
    except Exception as e:
        logging.exception("FastAPI startup failed: %s", e)
        raise

    yield

    # Shutdown
    try:
        # Update health status to shutting down
        try:
            from ..bot.main import update_health_status

            update_health_status("shutting_down")
        except Exception:
            pass

        if bot:
            await bot_on_shutdown(bot)
            try:
                await bot.delete_webhook()
            except Exception as e:
                logging.warning("Failed to delete webhook: %s", e)

            if hasattr(bot, "session") and bot.session:
                await bot.session.close()

        if dp:
            await dp.emit_shutdown()

        await close_db()
        logging.info("FastAPI server shutdown completed")
    except Exception as e:
        logging.exception("FastAPI shutdown failed: %s", e)


app = FastAPI(
    title="BuddyGym API",
    description="API for BuddyGym Telegram bot",
    version=__import__("buddy_gym_bot").__version__,
    lifespan=lifespan,
)

# CORS setup: allow webapp, Telegram, and web.telegram.org
allowed: set[str] = set()
try:
    u = urlparse(SETTINGS.WEBAPP_URL)
    origin = f"{u.scheme}://{u.netloc}"
    allowed.add(origin)
except Exception:
    pass
allowed.add("https://t.me")
allowed.add("https://web.telegram.org")

# Add local development origins
allowed.add("http://localhost:3000")
allowed.add("http://127.0.0.1:3000")

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

# Telegram bot setup - will be initialized in startup
bot: Bot | None = None
dp: Dispatcher | None = None

WEBHOOK_PATH = urlparse(SETTINGS.WEBHOOK_URL).path if SETTINGS.WEBHOOK_URL else "/bot"


@app.post(WEBHOOK_PATH)
async def telegram_webhook(update: dict) -> dict:
    """Handle Telegram webhook updates."""
    if not bot or not dp:
        return {"ok": False, "error": "bot_not_initialized"}

    try:
        tg_update = Update.model_validate(update)
        await dp.feed_update(bot, tg_update)
        return {"ok": True}
    except Exception as e:
        logging.exception("Webhook update processing failed: %s", e)
        return {"ok": False, "error": "update_processing_failed"}


@app.exception_handler(Exception)
async def global_exc_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler: log and return a generic error response.
    """
    logging.exception("Unhandled error in %s: %s", request.url, exc)
    return JSONResponse(
        {"ok": False, "error": "internal_error", "message": "Internal server error"},
        status_code=500,
    )


@app.get("/healthz")
async def healthz() -> dict:
    """
    Enhanced health check endpoint with system status.
    """
    try:
        # Get system metrics
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Get bot health status if available
        bot_status = "unknown"
        try:
            from ..bot.main import get_health_status

            bot_health = get_health_status()
            bot_status = bot_health.get("status", "unknown")
        except Exception:
            bot_status = "unavailable"

        # Check if we're healthy
        is_healthy = (
            memory.percent < 90  # Memory usage under 90%
            and cpu_percent < 95  # CPU usage under 95%
            and bot_status in ["healthy", "starting"]
        )

        return {
            "ok": is_healthy,
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": datetime.now(UTC).isoformat(),
            "system": {
                "memory_percent": round(memory.percent, 1),
                "memory_available_mb": round(memory.available / 1024 / 1024, 1),
                "cpu_percent": round(cpu_percent, 1),
            },
            "bot": {"status": bot_status},
        }

    except Exception as e:
        logging.exception("Health check failed: %s", e)
        return {
            "ok": False,
            "status": "error",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }


@app.get("/")
async def root() -> dict:
    """
    Root endpoint with API information.
    """
    return {
        "ok": True,
        "name": "BuddyGym API",
        "version": "0.2.0",
        "description": "Telegram bot API for workout tracking and planning",
    }


# Routers for API endpoints
app.include_router(r_exercises, prefix="/api/v1", tags=["exercises"])
app.include_router(r_workout, prefix="/api/v1", tags=["workout"])
app.include_router(r_share, prefix="/api/v1", tags=["share"])
app.include_router(r_plan, prefix="/api/v1", tags=["plan"])
app.include_router(r_schedule, prefix="/api/v1", tags=["schedule"])
