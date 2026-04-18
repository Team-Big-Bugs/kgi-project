from __future__ import annotations

from datetime import time

from sqlalchemy import Boolean, Enum, ForeignKey, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class AgentPreference(TimestampMixin, Base):
    __tablename__ = "agent_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    preferred_channel: Mapped[str] = mapped_column(
        Enum("PUSH", "EMAIL", "LINE", name="channel_type"), default="EMAIL", nullable=False
    )
    dnd_start_time: Mapped[time | None] = mapped_column(Time())
    dnd_end_time: Mapped[time | None] = mapped_column(Time())
    is_opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    peak_learning_time: Mapped[time] = mapped_column(Time(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="preference")
