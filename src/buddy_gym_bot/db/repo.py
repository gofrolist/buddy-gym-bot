"""
Async SQLAlchemy repository for BuddyGym database operations.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import SETTINGS
from .models import Base, Referral, ReferralStatus, SetRow, User, UserPlan, WorkoutSession

_engine: AsyncEngine | None = None
_session: async_sessionmaker[AsyncSession] | None = None


def _prepare_url(url: str) -> tuple[str, dict]:
    """Return sanitized DB URL and connect args.

    Extracts common SSL query parameters and passes them as ``connect_args``
    for ``psycopg``. ``ssl=false`` becomes ``sslmode=disable``.
    """

    url_obj = make_url(url)
    query = dict(url_obj.query)
    connect_args: dict[str, object] = {}

    # SSL normalization
    sslmode = query.pop("sslmode", None)
    ssl_val = query.pop("ssl", None)
    if ssl_val is not None:
        sslmode = "disable" if str(ssl_val).lower() in {"0", "false", "off", "no"} else "require"
    if sslmode:
        connect_args["sslmode"] = sslmode

    # 🔑 PgBouncer-friendly settings by driver
    driver = url_obj.drivername or ""
    if driver.startswith("postgresql+psycopg"):
        connect_args.setdefault("prepare_threshold", 0)  # psycopg3
    elif driver.startswith("postgresql+asyncpg"):
        connect_args.setdefault("statement_cache_size", 0)  # asyncpg

    url_obj = url_obj.set(query=query)
    return url_obj.render_as_string(hide_password=False), connect_args


async def _run_migrations(conn: Any) -> None:
    """Execute .sql migration files sequentially.

    Looks for a ``migrations`` directory bundled with the package first,
    falling back to the repository root when running from source.
    """

    paths: list[Any] = []

    try:
        pkg_migrations = resources.files("buddy_gym_bot").joinpath("migrations")
        if pkg_migrations.is_dir():
            paths.extend(p for p in pkg_migrations.iterdir() if p.name.endswith(".sql"))
    except Exception:
        pass

    if not paths:
        fs_dir = Path(__file__).resolve().parents[2] / "migrations"
        if fs_dir.is_dir():
            paths = [p for p in fs_dir.iterdir() if p.suffix == ".sql"]

    for path in sorted(paths, key=lambda p: p.name):
        sql = path.read_text(encoding="utf-8")
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.run_sync(lambda sync_conn, s=stmt: sync_conn.exec_driver_sql(s))  # type: ignore


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
    db_url, connect_args = _prepare_url(SETTINGS.DATABASE_URL)
    _engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    _session = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        # For in-memory SQLite, skip migrations (faster, portable) and create tables from models
        should_use_create_all = False
        try:
            url_obj = make_url(db_url)
            if url_obj.drivername.startswith("sqlite") and (
                url_obj.database in {":memory:", "", None} or ":memory:" in db_url
            ):
                should_use_create_all = True
        except Exception:
            pass

        if should_use_create_all:
            await conn.run_sync(Base.metadata.create_all)
        else:
            # discover migrations
            have_migrations = False
            try:
                pkg_migrations = resources.files("buddy_gym_bot").joinpath("migrations")
                have_migrations = pkg_migrations.is_dir()
            except Exception:
                pass
            if not have_migrations:
                fs_dir = Path(__file__).resolve().parents[2] / "migrations"
                have_migrations = fs_dir.is_dir()

            if have_migrations:
                await _run_migrations(conn)
            else:
                await conn.run_sync(Base.metadata.create_all)


def get_session() -> async_sessionmaker[AsyncSession]:
    """
    Get the async sessionmaker. Raises if DB is not initialized.
    """
    if not _session:
        raise RuntimeError("DB not initialized; call init_db() first")
    return _session


async def close_db() -> None:
    """Dispose of the database engine and reset session state."""

    global _engine, _session
    if _engine:
        await _engine.dispose()
    _engine = None
    _session = None


async def upsert_user(tg_user_id: int, handle: str | None, lang: str | None) -> User:
    """
    Upsert a user by Telegram ID.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(select(User).where(User.tg_user_id == tg_user_id))
        user = res.scalar_one_or_none()
        if user is None:
            user = User(tg_user_id=tg_user_id, handle=handle, last_lang=(lang or "en")[:2])
            s.add(user)
            await s.commit()
            # No need to refresh after commit - the user object is already populated
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


async def get_user_by_tg(tg_user_id: int) -> User | None:
    """
    Get a user by Telegram ID.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(select(User).where(User.tg_user_id == tg_user_id))
        return res.scalar_one_or_none()


async def get_user_plan(user_id: int) -> dict[str, Any] | None:
    """Return the latest stored plan for a user."""
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(select(UserPlan).where(UserPlan.user_id == user_id))
        up = res.scalar_one_or_none()
        return up.plan if up else None


async def upsert_user_plan(user_id: int, plan: dict[str, Any]) -> None:
    """Insert or update the stored plan for a user."""
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(select(UserPlan).where(UserPlan.user_id == user_id))
        up = res.scalar_one_or_none()
        if up is None:
            up = UserPlan(
                user_id=user_id,
                plan=plan,
                days_per_week=plan.get("days_per_week", 0),
                days=plan.get("days", []),
            )
            s.add(up)
        else:
            up.plan = plan
            up.days_per_week = plan.get("days_per_week", 0)
            up.days = plan.get("days", [])
            up.updated_at = datetime.now(UTC)
        await s.commit()


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
        res2 = await s.execute(select(User).where(User.tg_user_id == invitee_tg_id))
        invitee = res2.scalar_one_or_none()
        if invitee is None:
            invitee = User(tg_user_id=invitee_tg_id, last_lang="en")
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
        res_inv = await s.execute(select(User).where(User.tg_user_id == invitee_tg_id))
        invitee = res_inv.scalar_one_or_none()
        if not invitee:
            return False
        # Invitee must have logged at least one set before referral is fulfilled
        if not await _user_has_any_sets(invitee.id):
            return False
        res_ref = await s.execute(
            select(Referral)
            .where(
                Referral.invitee_user_id == invitee.id, Referral.status == ReferralStatus.PENDING
            )
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
        ref.status = ReferralStatus.FULFILLED
        ref.fulfilled_at = datetime.now(UTC)
        await s.commit()
        return True


async def start_session_and_append_set(
    user_id: int,
    exercise: str,
    weight_kg: float,
    input_weight: float,
    input_unit: str,
    reps: int,
    rpe: float | None,
    is_warmup: bool = False,
    title: str | None = None,
) -> tuple[WorkoutSession, SetRow]:
    """
    Start a new workout session and append a set in a single transaction.
    This is more efficient than separate operations.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        # Create session
        ws = WorkoutSession(user_id=user_id, title=title or "Quick Log")
        s.add(ws)
        await s.flush()  # Get the ID without committing

        # Create set row
        row = SetRow(
            session_id=ws.id,
            exercise=exercise,
            weight_kg=weight_kg,
            input_weight=input_weight,
            input_unit=input_unit,
            reps=reps,
            rpe=rpe,
            is_warmup=is_warmup,
        )
        s.add(row)

        # Single commit for both operations
        await s.commit()
        await s.refresh(ws)
        await s.refresh(row)

        return ws, row


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
    input_weight: float,
    input_unit: str,
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
            input_weight=input_weight,
            input_unit=input_unit,
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


async def get_user_sessions(user_id: int) -> list[WorkoutSession]:
    """
    Get all workout sessions for a user with their sets.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        res = await s.execute(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user_id)
            .order_by(WorkoutSession.started_at.desc())
        )
        sessions = list(res.scalars().all())

        # Load sets for each session
        for session in sessions:
            await s.refresh(session, attribute_names=["sets"])

        return sessions
