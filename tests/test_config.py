import os

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from buddy_gym_bot.config import _norm_db_url


def test_norm_db_url_sqlite_to_aiosqlite() -> None:
    assert _norm_db_url("sqlite:///test.db") == "sqlite+aiosqlite:///test.db"
    assert _norm_db_url("sqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"
    # already using aiosqlite should stay untouched
    assert _norm_db_url("sqlite+aiosqlite:///test.db") == "sqlite+aiosqlite:///test.db"
