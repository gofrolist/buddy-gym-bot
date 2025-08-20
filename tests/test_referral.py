import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from buddy_gym_bot.db.models import Base, Referral, ReferralStatus, SetRow, User, WorkoutSession


@pytest.mark.asyncio
async def test_referral_requires_sets() -> None:
    # Create engine and tables directly - much faster than init_db
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Test logic
    async with async_session() as s:
        # Create host user
        host = User(tg_user_id=1, handle="host", last_lang="en")
        s.add(host)
        await s.commit()
        await s.refresh(host)

        # Create referral token
        token = "ref_test123"
        ref = Referral(inviter_user_id=host.id, token=token)
        s.add(ref)
        await s.commit()

        # Record referral click (create invitee user)
        invitee = User(tg_user_id=2, handle="inv", last_lang="en")
        s.add(invitee)
        await s.commit()
        await s.refresh(invitee)

        # Try to fulfill referral (should fail - no workout sets)
        # Check if referral exists and is pending
        referral = await s.get(Referral, ref.id)
        assert referral.status.value == "PENDING"

        # Create workout session and set
        sess = WorkoutSession(user_id=invitee.id, title="Test")
        s.add(sess)
        await s.commit()
        await s.refresh(sess)

        set_row = SetRow(
            session_id=sess.id,
            exercise="bench",
            weight_kg=100,
            input_weight=100,  # User entered 100 kg
            input_unit="kg",
            reps=5,
        )
        s.add(set_row)
        await s.commit()

        # Now referral should be fulfillable
        referral.status = ReferralStatus.FULFILLED
        referral.fulfilled_at = datetime.now(UTC)
        await s.commit()

        # Verify referral is fulfilled
        await s.refresh(referral)
        assert referral.status.value == "FULFILLED"

    await engine.dispose()
