from __future__ import annotations

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class NotificationTemplate(TimestampMixin, Base):
    __tablename__ = "notification_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger_type: Mapped[str] = mapped_column(
        Enum("bio_rhythm_peak", "streak_warning", "spaced_repetition_due", name="trigger_type"), nullable=False
    )
    channel_type: Mapped[str] = mapped_column(
        Enum("PUSH", "EMAIL", "LINE", name="template_channel_type"), nullable=False
    )
    title_template: Mapped[str] = mapped_column(String(255), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    dispatch_logs: Mapped[list["DispatchLog"]] = relationship(back_populates="template")
