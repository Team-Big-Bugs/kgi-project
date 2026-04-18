from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.notification_template import NotificationTemplate
from app.db.models.user import User


def dashboard_metrics(db: Session) -> dict[str, int]:
    return {
        "agents": db.scalar(select(func.count()).select_from(User).where(User.role == "agent")) or 0,
        "templates": db.scalar(select(func.count()).select_from(NotificationTemplate)) or 0,
        "pending_assignments": db.scalar(
            select(func.count()).select_from(LearningAssignment).where(LearningAssignment.completed_at.is_(None))
        )
        or 0,
        "sent_today": db.scalar(
            select(func.count()).select_from(DispatchLog).where(
                DispatchLog.sent_at.is_not(None),
                DispatchLog.sent_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
            )
        )
        or 0,
    }


def list_templates(db: Session) -> list[NotificationTemplate]:
    return list(db.scalars(select(NotificationTemplate).order_by(NotificationTemplate.channel_type)))


def list_dispatches(db: Session, limit: int = 50) -> list[DispatchLog]:
    stmt = select(DispatchLog).order_by(DispatchLog.scheduled_dispatch_time.desc()).limit(limit)
    return list(db.scalars(stmt))


def list_agents(db: Session) -> list[User]:
    return list(db.scalars(select(User).where(User.role == "agent").order_by(User.name.asc())))
