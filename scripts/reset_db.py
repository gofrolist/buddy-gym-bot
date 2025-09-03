#!/usr/bin/env python3
"""
Reset database script for local development.
This script will drop all tables and recreate them with the correct schema.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set default environment variables for local development
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./local_dev.db")
os.environ.setdefault("ADMIN_CHAT_ID", "123456789")

from buddy_gym_bot.db import repo
from buddy_gym_bot.db.models import Base


async def reset_database():
    """Reset the database by dropping all tables and recreating them."""
    print("🔄 Resetting database...")

    # Set environment to force SQLite mode
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./local_dev.db"

    # Initialize database connection
    await repo.init_db()

    # Get the engine
    engine = repo._engine
    if not engine:
        print("❌ Failed to initialize database engine")
        return

    async with engine.begin() as conn:
        # Drop all tables
        print("🗑️  Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)

        # Create all tables from models (skip migrations for SQLite)
        print("🏗️  Creating tables from models...")
        await conn.run_sync(Base.metadata.create_all)

        print("✅ Database reset complete!")
        print("📊 Tables created:")

        # List created tables
        from sqlalchemy import text

        result = await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        )
        tables = result.fetchall()
        for table in tables:
            print(f"   - {table[0]}")


if __name__ == "__main__":
    asyncio.run(reset_database())
