from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(Enum("agent", "admin", name="user_role"), default="agent", nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    line_user_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    preference: Mapped["AgentPreference"] = relationship(back_populates="user", uselist=False)
    assignments: Mapped[list["LearningAssignment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    dispatch_logs: Mapped[list["DispatchLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    push_subscriptions: Mapped[list["WebPushSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    line_link_requests: Mapped[list["LineLinkRequest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
