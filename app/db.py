import psycopg
from contextlib import asynccontextmanager
from .settings import settings

@asynccontextmanager
async def get_conn():
    async with await psycopg.AsyncConnection.connect(settings.DATABASE_URL) as conn:
        yield conn