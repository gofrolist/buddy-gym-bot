"""
Async SQLAlchemy repository for BuddyGym database operations.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import SETTINGS
from .models import Base, Referral, SetRow, User, WorkoutSession

_engine: AsyncEngine | None = None
_session: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Initialize the async database engine and sessionmaker, and create tables if needed.
    """
    global _engine, _session
    if _engine:
        return
    if not SETTINGS.DATABASE_URL:
        logging.error("DATABASE_URL is required for DB initialization.")
        raise RuntimeError("DATABASE_URL is required")
    _engine = create_async_engine(
        SETTINGS.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,
        },
    )
    _session = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session() -> async_sessionmaker[AsyncSession]:
    """
    Get the async sessionmaker. Raises if DB is not initialized.
    """
    if not _session:
        raise RuntimeError("DB not initialized; call init_db() first")
    return _session


async def upsert_user(tg_id: int, handle: str | None, lang: str | None) -> User:
    """
    Insert or update a user by Telegram ID. Updates handle/lang if changed.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(select(User).where(User.tg_id == tg_id))
        user = res.scalar_one_or_none()
        if user is None:
            user = User(tg_id=tg_id, handle=handle, last_lang=(lang or "en")[:2])
            s.add(user)
            await s.commit()
            await s.refresh(user)
        else:
            changed = False
            if handle and user.handle != handle:
                user.handle = handle
                changed = True
            if lang and user.last_lang != (lang or "en")[:2]:
                user.last_lang = (lang or "en")[:2]
                changed = True
            if changed:
                await s.commit()
        return user


async def get_user_by_tg(tg_id: int) -> User | None:
    """
    Get a user by their Telegram ID.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()


async def ensure_referral_token(inviter_user_id: int) -> str:
    """
    Create a referral token for a user.
    """
    token_prefix = "ref_"
    token = token_prefix + secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    sessmaker = get_session()
    async with sessmaker() as s:
        ref = Referral(inviter_user_id=inviter_user_id, token=token)
        s.add(ref)
        await s.commit()
        return token


async def record_referral_click(invitee_tg_id: int, token: str) -> None:
    """
    Record a referral click and associate the invitee with the referral.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(select(Referral).where(Referral.token == token))
        ref = res.scalar_one_or_none()
        if not ref:
            return
        # create invitee if not exists
        res2 = await s.execute(select(User).where(User.tg_id == invitee_tg_id))
        invitee = res2.scalar_one_or_none()
        if invitee is None:
            invitee = User(tg_id=invitee_tg_id, last_lang="en")
            s.add(invitee)
            await s.flush()
        ref.invitee_user_id = invitee.id
        await s.commit()


async def _user_has_any_sets(user_id: int) -> bool:
    """
    Check if a user has any logged sets.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(
            select(func.count(SetRow.id))
            .join(WorkoutSession)
            .where(WorkoutSession.user_id == user_id)
        )
        return (res.scalar() or 0) > 0


async def fulfil_referral_for_invitee(invitee_tg_id: int) -> bool:
    """
    Fulfill a referral for an invitee if eligible, granting premium days to both users.
    Returns True if fulfilled, False otherwise.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res_inv = await s.execute(select(User).where(User.tg_id == invitee_tg_id))
        invitee = res_inv.scalar_one_or_none()
        if not invitee:
            return False
        res_ref = await s.execute(
            select(Referral)
            .where(Referral.invitee_user_id == invitee.id, Referral.status == "PENDING")
            .order_by(Referral.created_at.asc())
        )
        ref = res_ref.scalar_one_or_none()
        if not ref:
            return False
        # Add premium days to both
        res_host = await s.execute(select(User).where(User.id == ref.inviter_user_id))
        host = res_host.scalar_one_or_none()
        if not host:
            return False
        host.add_premium_days(ref.reward_days)
        invitee.add_premium_days(ref.reward_days)
        ref.status = "FULFILLED"
        ref.fulfilled_at = datetime.now(UTC)
        await s.commit()
        return True


async def start_session(user_id: int, title: str | None = None) -> WorkoutSession:
    """
    Start a new workout session for a user.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        ws = WorkoutSession(user_id=user_id, title=title)
        s.add(ws)
        await s.commit()
        await s.refresh(ws)
        return ws


async def append_set(
    session_id: int,
    exercise: str,
    weight_kg: float,
    reps: int,
    rpe: float | None,
    is_warmup: bool = False,
) -> SetRow:
    """
    Append a set to a workout session.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        row = SetRow(
            session_id=session_id,
            exercise=exercise,
            weight_kg=weight_kg,
            reps=reps,
            rpe=rpe,
            is_warmup=is_warmup,
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row


async def last_best_set(user_id: int, exercise: str) -> tuple[int, float, int] | None:
    """
    Get the best (heaviest x reps) set for a user and exercise.
    Returns (set_id, weight_kg, reps) or None.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(
            select(SetRow.id, SetRow.weight_kg, SetRow.reps)
            .join(WorkoutSession)
            .where(WorkoutSession.user_id == user_id, SetRow.exercise.ilike(exercise))
            .order_by((SetRow.weight_kg * SetRow.reps).desc())
            .limit(1)
        )
        row = res.first()
        return (row[0], row[1], row[2]) if row else None
