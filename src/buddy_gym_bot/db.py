"""Database connection helpers."""

import logging
from contextlib import asynccontextmanager

import psycopg

from .settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_conn():
    logger.debug("Opening database connection")
    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
        logger.debug("Database connection established")
        yield conn
