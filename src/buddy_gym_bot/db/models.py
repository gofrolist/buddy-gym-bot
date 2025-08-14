"""
SQLAlchemy ORM models for BuddyGym database tables.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, ForeignKey, Boolean, DateTime, Enum, UniqueConstraint

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

class User(Base):
    """User of the BuddyGym bot."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    handle: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tz: Mapped[str] = mapped_column(String(32), default="UTC")
    units: Mapped[str] = mapped_column(String(8), default="kg")
    last_lang: Mapped[str] = mapped_column(String(8), default="en")
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sessions: Mapped[list[WorkoutSession]] = relationship("WorkoutSession", back_populates="user")

    def add_premium_days(self, days: int) -> None:
        """Extend premium_until by a given number of days."""
        now = datetime.now(timezone.utc)
        start = self.premium_until if self.premium_until and self.premium_until > now else now
        self.premium_until = start + timedelta(days=days)

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_id={self.tg_id} handle={self.handle}>"

class ReferralStatus:
    """Referral status constants."""
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"

class Referral(Base):
    """Referral relationship between users."""
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(primary_key=True)
    inviter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invitee_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reward_days: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(16), default=ReferralStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Referral id={self.id} inviter={self.inviter_user_id} invitee={self.invitee_user_id} status={self.status}>"

class WorkoutSession(Base):
    """A workout session belonging to a user."""
    __tablename__ = "workout_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")
    sets: Mapped[list[SetRow]] = relationship("SetRow", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WorkoutSession id={self.id} user_id={self.user_id} title={self.title}>"

class SetRow(Base):
    """A single set performed in a workout session."""
    __tablename__ = "set_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"), index=True)
    exercise: Mapped[str] = mapped_column(String(120))
    weight_kg: Mapped[float] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(Integer)
    rpe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_warmup: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session: Mapped[WorkoutSession] = relationship("WorkoutSession", back_populates="sets")

    def __repr__(self) -> str:
        return f"<SetRow id={self.id} session_id={self.session_id} exercise={self.exercise} reps={self.reps}>"
