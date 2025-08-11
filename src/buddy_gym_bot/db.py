from contextlib import asynccontextmanager

import psycopg

from .settings import settings


@asynccontextmanager
async def get_conn():
    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
        yield conn
