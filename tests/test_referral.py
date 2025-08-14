import os

import pytest

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from buddy_gym_bot.db import repo


@pytest.mark.asyncio
async def test_referral_requires_sets() -> None:
    await repo.init_db()
    host = await repo.upsert_user(1, "host", "en")
    token = await repo.ensure_referral_token(host.id)
    await repo.record_referral_click(2, token)

    ok = await repo.fulfil_referral_for_invitee(2)
    assert ok is False

    invitee = await repo.upsert_user(2, "inv", "en")
    sess = await repo.start_session(invitee.id)
    await repo.append_set(sess.id, "bench", 100, 5, None)

    ok2 = await repo.fulfil_referral_for_invitee(2)
    assert ok2 is True
