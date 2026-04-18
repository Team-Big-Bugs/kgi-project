from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.agent_preference import AgentPreference
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.notification_template import NotificationTemplate
from app.db.models.user import User
from app.db.session import SessionLocal, engine


settings = get_settings()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    local_tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(local_tz)
    next_peak = now_local + timedelta(minutes=settings.seed_now_offset_minutes)

    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == str(settings.demo_admin_email)))
        if admin is None:
            admin = User(
                role="admin",
                name="Training Admin",
                email=str(settings.demo_admin_email),
                password_hash=hash_password(settings.demo_admin_password),
            )
            db.add(admin)
            db.flush()

        agent = db.scalar(select(User).where(User.email == str(settings.demo_agent_email)))
        if agent is None:
            agent = User(
                role="agent",
                name="Lin",
                email=str(settings.demo_agent_email),
                password_hash=hash_password(settings.demo_agent_password),
            )
            db.add(agent)
            db.flush()

        if agent.preference is None:
            db.add(
                AgentPreference(
                    user_id=agent.id,
                    preferred_channel="EMAIL",
                    dnd_start_time=datetime.strptime(settings.default_dnd_start_time, "%H:%M").time(),
                    dnd_end_time=datetime.strptime(settings.default_dnd_end_time, "%H:%M").time(),
                    peak_learning_time=next_peak.time().replace(second=0, microsecond=0),
                )
            )

        has_assignment = db.scalar(select(LearningAssignment).where(LearningAssignment.user_id == agent.id))
        if has_assignment is None:
            db.add_all(
                [
                    LearningAssignment(
                        user_id=agent.id,
                        module_title="Travel Insurance Essentials",
                        task_type="mandatory_module",
                        due_at=now_local.astimezone(timezone.utc) - timedelta(minutes=5),
                    ),
                    LearningAssignment(
                        user_id=agent.id,
                        module_title="Investment-Linked Product Recall Quiz",
                        task_type="memory_recall",
                        due_at=now_local.astimezone(timezone.utc) - timedelta(minutes=2),
                    ),
                ]
            )

        existing_templates = list(db.scalars(select(NotificationTemplate)))
        if not existing_templates:
            db.add_all(
                [
                    NotificationTemplate(
                        trigger_type="bio_rhythm_peak",
                        channel_type="EMAIL",
                        title_template="Hey {{agent_name}}, your peak learning window is close",
                        body_template=(
                            "Spend 7 focused minutes on {{module_title}} before your "
                            "{{peak_learning_time}} peak window closes."
                        ),
                    ),
                    NotificationTemplate(
                        trigger_type="bio_rhythm_peak",
                        channel_type="PUSH",
                        title_template="{{agent_name}}, your Streak Shield is vulnerable",
                        body_template="Spend 7 minutes on {{module_title}} before {{peak_learning_time}}.",
                    ),
                    NotificationTemplate(
                        trigger_type="bio_rhythm_peak",
                        channel_type="LINE",
                        title_template="Peak window almost here, {{agent_name}}",
                        body_template="Review {{module_title}} before {{peak_learning_time}}.",
                    ),
                    NotificationTemplate(
                        trigger_type="spaced_repetition_due",
                        channel_type="EMAIL",
                        title_template="{{agent_name}}, quick recall check due",
                        body_template="A 2-minute reinforcement quiz is ready for {{module_title}}.",
                    ),
                    NotificationTemplate(
                        trigger_type="spaced_repetition_due",
                        channel_type="PUSH",
                        title_template="Recall quiz ready for {{agent_name}}",
                        body_template="Your next repetition for {{module_title}} is due now.",
                    ),
                    NotificationTemplate(
                        trigger_type="spaced_repetition_due",
                        channel_type="LINE",
                        title_template="{{agent_name}}, memory recall time",
                        body_template="Open {{module_title}} for a quick reinforcement sprint.",
                    ),
                ]
            )

        db.commit()


if __name__ == "__main__":
    main()
