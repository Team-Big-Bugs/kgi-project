from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agent_preference import AgentPreference
from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.user import User
from app.db.models.web_push_subscription import WebPushSubscription


def get_agent_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_or_create_preference(
    db: Session,
    *,
    user_id: int,
    preferred_channel: str = "EMAIL",
    dnd_start_time: time | None = None,
    dnd_end_time: time | None = None,
    peak_learning_time: time,
) -> AgentPreference:
    preference = db.get(AgentPreference, user_id)
    if preference is None:
        preference = AgentPreference(
            agent_id=user_id,
            preferred_channel=preferred_channel,
            dnd_start_time=dnd_start_time,
            dnd_end_time=dnd_end_time,
            peak_learning_time=peak_learning_time,
        )
        db.add(preference)
        db.commit()
        db.refresh(preference)
    return preference


def update_preference(
    db: Session,
    *,
    user_id: int,
    preferred_channel: str,
    dnd_start_time: time | None,
    dnd_end_time: time | None,
    is_opted_out: bool,
    peak_learning_time: time,
) -> AgentPreference:
    preference = db.get(AgentPreference, user_id)
    if preference is None:
        preference = AgentPreference(agent_id=user_id, peak_learning_time=peak_learning_time)

    preference.preferred_channel = preferred_channel
    preference.dnd_start_time = dnd_start_time
    preference.dnd_end_time = dnd_end_time
    preference.is_opted_out = is_opted_out
    preference.peak_learning_time = peak_learning_time
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


def list_pending_assignments(db: Session, user_id: int) -> list[LearningAssignment]:
    stmt = (
        select(LearningAssignment)
        .where(LearningAssignment.user_id == user_id, LearningAssignment.completed_at.is_(None))
        .order_by(LearningAssignment.due_at.asc())
    )
    return list(db.scalars(stmt))


def list_recent_dispatches(db: Session, user_id: int, limit: int = 10) -> list[DispatchLog]:
    stmt = (
        select(DispatchLog)
        .where(DispatchLog.agent_id == user_id)
        .order_by(DispatchLog.scheduled_dispatch_time.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def active_push_subscription(db: Session, user_id: int) -> WebPushSubscription | None:
    stmt = select(WebPushSubscription).where(
        WebPushSubscription.user_id == user_id,
        WebPushSubscription.is_active.is_(True),
    )
    return db.scalar(stmt)


def mark_assignment_completed(db: Session, assignment: LearningAssignment) -> LearningAssignment:
    assignment.completed_at = datetime.now(timezone.utc)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment
