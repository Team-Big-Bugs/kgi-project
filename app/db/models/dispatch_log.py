from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class DispatchLog(TimestampMixin, Base):
    __tablename__ = "dispatch_logs"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_dispatch_logs_dedupe_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    learning_assignment_id: Mapped[int] = mapped_column(ForeignKey("learning_assignments.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("notification_templates.id"), nullable=False)
    channel_type: Mapped[str] = mapped_column(
        Enum("PUSH", "EMAIL", "LINE", name="dispatch_channel_type"), nullable=False
    )
    scheduled_dispatch_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(Enum("queued", "sent", "failed", name="dispatch_status"), nullable=False)
    tracking_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="dispatch_logs")
    assignment: Mapped["LearningAssignment"] = relationship(back_populates="dispatch_logs")
    template: Mapped["NotificationTemplate"] = relationship(back_populates="dispatch_logs")
