"""
Async SQLAlchemy repository for BuddyGym database operations.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar

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

# Type variable for the retry decorator
F = TypeVar("F", bound=Callable[..., Any])


# Type alias for session objects that can be returned safely
class SessionWithSets:
    """Simple session object with sets that can be returned safely."""

    def __init__(self, data: dict[str, Any]):
        self.id: int = data["id"]
        self.user_id: int = data["user_id"]
        self.title: str = data["title"]
        self.started_at: datetime = data["started_at"]
        self.ended_at: datetime | None = data["ended_at"]
        self.sets: list[SetRow] = data["sets"]


def retry_on_connection_error(max_retries: int = 3, delay: float = 0.1):
    """
    Decorator to retry database operations on connection errors.
    Useful for handling transient connection issues.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # Check if it's a connection-related error
                    if any(
                        keyword in str(e).lower()
                        for keyword in [
                            "connection",
                            "server closed",
                            "connection closed",
                            "operationalerror",
                            "timeout",
                        ]
                    ):
                        last_exception = e
                        if attempt < max_retries - 1:
                            # Exponential backoff
                            wait_time = delay * (2**attempt)
                            logging.warning(
                                "Database connection error on attempt %d/%d, retrying in %.2fs: %s",
                                attempt + 1,
                                max_retries,
                                wait_time,
                                e,
                            )
                            await asyncio.sleep(wait_time)
                            continue
                    # If it's not a connection error or we've exhausted retries, re-raise
                    raise
            # If we get here, all retries failed
            if last_exception:
                raise last_exception
            # This should never happen, but just in case
            raise RuntimeError("Retry mechanism failed unexpectedly")

        return wrapper  # type: ignore

    return decorator


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
        pool_recycle=3600,  # Recycle connections every hour
        pool_timeout=30,  # Wait up to 30 seconds for available connection
        max_overflow=10,  # Allow up to 10 additional connections beyond pool_size
        pool_size=20,  # Maintain up to 20 connections in the pool
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
    is_completed: bool = True,  # Default to completed since sets are marked complete when created
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
            is_completed=is_completed,  # Include completion status
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
    is_completed: bool = True,  # Default to completed since sets are marked complete when created
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
            is_completed=is_completed,  # Include completion status
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


@retry_on_connection_error(max_retries=3, delay=0.1)
async def get_user_sessions(user_id: int) -> list[WorkoutSession]:
    """
    Get all workout sessions for a user with their sets.
    Optimized to avoid individual refresh calls that can cause connection issues.
    """
    sessmaker = get_session()
    async with sessmaker() as s:
        # Use a single query with JOIN to fetch sessions and sets together
        # This avoids the need for individual refresh calls
        res = await s.execute(
            select(WorkoutSession, SetRow)
            .join(SetRow, WorkoutSession.id == SetRow.session_id, isouter=True)
            .where(WorkoutSession.user_id == user_id)
            .order_by(WorkoutSession.started_at.desc(), SetRow.id)
        )

        # Group results by session
        sessions_dict = {}
        for row in res:
            session, set_row = row
            if session.id not in sessions_dict:
                sessions_dict[session.id] = session
                sessions_dict[session.id].sets = []

            if set_row:  # Only add if there's a set
                sessions_dict[session.id].sets.append(set_row)

        # Convert to list and sort by start time
        sessions = list(sessions_dict.values())
        sessions.sort(key=lambda s: s.started_at, reverse=True)

        return sessions


@retry_on_connection_error(max_retries=3, delay=0.1)
async def get_active_session(user_id: int, hours_threshold: int = 2) -> SessionWithSets | None:
    """
    Get the most recent active workout session for a user.
    A session is considered active if it started within the last N hours and hasn't ended.
    Optimized to avoid individual refresh calls that can cause connection issues.
    """
    from datetime import UTC, datetime, timedelta

    sessmaker = get_session()
    async with sessmaker() as s:
        # Calculate the threshold time
        threshold_time = datetime.now(UTC) - timedelta(hours=hours_threshold)

        # First, find the active session
        session_res = await s.execute(
            select(WorkoutSession)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= threshold_time,
                WorkoutSession.ended_at.is_(None),  # Session hasn't ended
            )
            .order_by(WorkoutSession.started_at.desc())
            .limit(1)
        )

        session = session_res.scalar_one_or_none()
        if not session:
            return None

        # Now fetch all sets for this session in a separate query
        sets_res = await s.execute(
            select(SetRow).where(SetRow.session_id == session.id).order_by(SetRow.id)
        )

        # Create a new session object with the sets data
        # This avoids ORM context issues
        session_data = {
            "id": session.id,
            "user_id": session.user_id,
            "title": session.title,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "sets": list(sets_res.scalars().all()),
        }

        return SessionWithSets(session_data)
