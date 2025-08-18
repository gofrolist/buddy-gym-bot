"""
SQLAlchemy ORM models for BuddyGym database tables.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class User(Base):
    """User model representing a Telegram user."""

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )  # Explicitly specify autoincrement
    tg_user_id: Mapped[int] = mapped_column(
        unique=True, index=True
    )  # Changed from tg_id to tg_user_id
    handle: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Changed from String(32) to String(64)
    tz: Mapped[str] = mapped_column(
        String(32), default="UTC"
    )  # Changed from nullable=True to default="UTC"
    units: Mapped[str] = mapped_column(String(8), default="kg")  # Added back the units field
    last_lang: Mapped[str] = mapped_column(
        String(8), default="en"
    )  # Changed from String(5) to String(8)
    premium_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    sessions: Mapped[list[WorkoutSession]] = relationship("WorkoutSession", back_populates="user")
    referrals: Mapped[list[Referral]] = relationship(
        "Referral", foreign_keys="Referral.inviter_user_id"
    )

    def add_premium_days(self, days: int) -> None:
        """Add premium days to the user."""
        start = self.premium_until or datetime.now(UTC)
        self.premium_until = start + timedelta(days=days)

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_user_id={self.tg_user_id} handle={self.handle}>"


# CHANGE: Converted to str-enum for better JSON/serialization and clearer typing
class ReferralStatus(str, enum.Enum):
    """Referral status constants."""

    PENDING = "PENDING"
    FULFILLED = "FULFILLED"


class Referral(Base):
    """Referral relationship between users."""

    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )  # Explicitly specify autoincrement
    inviter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invitee_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reward_days: Mapped[int] = mapped_column(Integer, default=30)
    # CHANGE: Using SQLAlchemy Enum with native_enum=False for SQLite compatibility
    status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(
            ReferralStatus,
            name="referral_status",  # stable name for Alembic
            native_enum=False,  # critical for SQLite
            create_constraint=True,  # adds CHECK(...) on SQLite
            validate_strings=True,
        ),
        default=ReferralStatus.PENDING,
        server_default=text("'PENDING'"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Referral id={self.id} inviter={self.inviter_user_id} "
            f"invitee={self.inviter_user_id} status={self.status.value}>"
        )


class WorkoutSession(Base):
    """A workout session belonging to a user."""

    __tablename__ = "workout_sessions"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )  # Explicitly specify autoincrement
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")
    sets: Mapped[list[SetRow]] = relationship(
        "SetRow", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WorkoutSession id={self.id} user_id={self.user_id} title={self.title}>"


class SetRow(Base):
    """A single set performed in a workout session."""

    __tablename__ = "set_rows"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )  # Explicitly specify autoincrement
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"), index=True)
    exercise: Mapped[str] = mapped_column(String(120))
    weight_kg: Mapped[float] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(Integer)
    rpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_warmup: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    session: Mapped[WorkoutSession] = relationship("WorkoutSession", back_populates="sets")

    def __repr__(self) -> str:
        return f"<SetRow id={self.id} session_id={self.session_id} exercise={self.exercise} reps={self.reps}>"


class UserPlan(Base):
    """Persisted workout plan for a user."""

    __tablename__ = "user_plans"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON)
    days_per_week: Mapped[int] = mapped_column(Integer)
    days: Mapped[list[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover - repr is trivial
        return f"<UserPlan user_id={self.user_id} days_per_week={self.days_per_week}>"
