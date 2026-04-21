from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.agent_preference import AgentPreference
from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.notification_template import NotificationTemplate
from app.db.models.user import User
from app.services.dispatch import DispatchOrchestrator


logger = get_logger(__name__)
settings = get_settings()


@dataclass
class SchedulerStats:
    considered: int = 0
    queued: int = 0
    sent: int = 0
    failed: int = 0
    skipped_opt_out: int = 0
    skipped_dnd: int = 0
    skipped_peak_window: int = 0
    skipped_duplicate: int = 0


def _now_local(now_utc: datetime | None = None) -> datetime:
    current = now_utc or datetime.now(timezone.utc)
    return current.astimezone(ZoneInfo(settings.timezone))


def _is_time_in_window(local_time: time, start: time | None, end: time | None) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= local_time <= end
    return local_time >= start or local_time <= end


def _within_peak_window(local_now: datetime, peak_learning_time: time) -> bool:
    peak_datetime = local_now.replace(
        hour=peak_learning_time.hour, minute=peak_learning_time.minute, second=0, microsecond=0
    )
    window_start = peak_datetime - timedelta(minutes=settings.nudge_lead_minutes)
    return window_start <= local_now <= peak_datetime


def _dispatch_dedupe_key(*, agent_id: int, assignment_id: int, channel_type: str, scheduled_date: str) -> str:
    return f"{agent_id}:{assignment_id}:{channel_type}:{scheduled_date}"


def query_due_assignments(db: Session, now_utc: datetime | None = None) -> list[LearningAssignment]:
    current = now_utc or datetime.now(timezone.utc)
    stmt: Select[tuple[LearningAssignment]] = (
        select(LearningAssignment)
        .options(joinedload(LearningAssignment.user).joinedload(User.preference))
        .where(and_(LearningAssignment.completed_at.is_(None), LearningAssignment.due_at <= current))
    )
    return list(db.scalars(stmt))


def run_scheduler(db: Session, now_utc: datetime | None = None) -> SchedulerStats:
    current = now_utc or datetime.now(timezone.utc)
    local_now = _now_local(current)
    stats = SchedulerStats()
    orchestrator = DispatchOrchestrator(db)

    templates = {
        (template.trigger_type, template.channel_type): template
        for template in db.scalars(select(NotificationTemplate).where(NotificationTemplate.is_active.is_(True)))
    }

    for assignment in query_due_assignments(db, current):
        user = assignment.user
        preference = user.preference if user else None
        stats.considered += 1

        if not user or not preference:
            stats.failed += 1
            continue

        if preference.is_opted_out:
            stats.skipped_opt_out += 1
            continue

        if _is_time_in_window(local_now.time(), preference.dnd_start_time, preference.dnd_end_time):
            stats.skipped_dnd += 1
            continue

        if not _within_peak_window(local_now, preference.peak_learning_time):
            stats.skipped_peak_window += 1
            continue

        trigger_type = "spaced_repetition_due" if assignment.task_type == "memory_recall" else "bio_rhythm_peak"
        template = templates.get((trigger_type, preference.preferred_channel))
        if template is None:
            stats.failed += 1
            continue

        dedupe_key = _dispatch_dedupe_key(
            agent_id=user.id,
            assignment_id=assignment.id,
            channel_type=preference.preferred_channel,
            scheduled_date=local_now.strftime("%Y-%m-%d"),
        )
        existing = db.scalar(select(DispatchLog).where(DispatchLog.dedupe_key == dedupe_key))
        if existing:
            stats.skipped_duplicate += 1
            continue

        dispatch = orchestrator.create_dispatch_log(
            user=user,
            preference=preference,
            assignment=assignment,
            template=template,
            scheduled_dispatch_time=current,
            dedupe_key=dedupe_key,
        )
        stats.queued += 1
        result = orchestrator.send_dispatch(dispatch)
        dispatch.status = result.status
        dispatch.failure_reason = result.failure_reason
        if result.status == "sent":
            stats.sent += 1
        else:
            stats.failed += 1
        db.add(dispatch)
        db.commit()

    logger.info("Scheduler finished: %s", stats)
    return stats
