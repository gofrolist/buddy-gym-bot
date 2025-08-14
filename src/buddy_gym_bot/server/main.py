"""
BuddyGym FastAPI server main entrypoint.
Handles CORS, static webapp, error handling, and API routers.
"""

from __future__ import annotations
import logging, os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .routes.exercises import router as r_exercises
from .routes.workout import router as r_workout
from .routes.share import router as r_share
from ..config import SETTINGS
from ..logging_setup import setup_logging
from ..db import repo

app = FastAPI(title="BuddyGym API")

# CORS setup: allow webapp, Telegram, and web.telegram.org
allowed = set()
try:
    from urllib.parse import urlparse
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

@app.on_event("startup")
async def _startup() -> None:
    """
    FastAPI startup event: set up logging and initialize the database.
    """
    setup_logging()
    try:
        await repo.init_db()
    except Exception as e:
        logging.exception("DB init failed")

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
