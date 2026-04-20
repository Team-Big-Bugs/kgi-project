from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models.agent_preference import AgentPreference
from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.notification_template import NotificationTemplate
from app.db.models.user import User
from app.services.channels.email import EmailSender
from app.services.channels.line import LineSender
from app.services.channels.web_push import WebPushSender
from app.services.template_service import render_template_message


logger = get_logger(__name__)


@dataclass
class DispatchResult:
    status: str
    failure_reason: str | None = None


class DispatchOrchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.email_sender = EmailSender()
        self.line_sender = LineSender()
        self.web_push_sender = WebPushSender()

    def create_dispatch_log(
        self,
        *,
        user: User,
        preference: AgentPreference,
        assignment: LearningAssignment,
        template: NotificationTemplate,
        scheduled_dispatch_time: datetime,
        dedupe_key: str,
    ) -> DispatchLog:
        dispatch = DispatchLog(
            agent_id=user.id,
            learning_assignment_id=assignment.id,
            template_id=template.template_id,
            channel_type=preference.preferred_channel,
            scheduled_dispatch_time=scheduled_dispatch_time,
            status="queued",
            tracking_token=token_urlsafe(24),
            dedupe_key=dedupe_key,
        )
        self.db.add(dispatch)
        self.db.flush()
        return dispatch

    def send_dispatch(self, dispatch: DispatchLog) -> DispatchResult:
        user = self.db.get(User, dispatch.agent_id)
        assignment = self.db.get(LearningAssignment, dispatch.learning_assignment_id)
        template = self.db.get(NotificationTemplate, dispatch.template_id)
        preference = self.db.scalar(select(AgentPreference).where(AgentPreference.agent_id == dispatch.agent_id))

        if not user or not assignment or not template or not preference:
            return DispatchResult(status="failed", failure_reason="Missing dispatch dependencies")

        title, body = render_template_message(
            template,
            user=user,
            assignment=assignment,
            peak_learning_time=preference.peak_learning_time.strftime("%H:%M"),
        )
        tracking_url = f"/track/{dispatch.tracking_token}?assignment_id={assignment.id}"

        try:
            if dispatch.channel_type == "EMAIL":
                self.email_sender.send(user=user, title=title, body=body, tracking_url=tracking_url)
            elif dispatch.channel_type == "LINE":
                self.line_sender.send(user=user, title=title, body=body, tracking_url=tracking_url)
            elif dispatch.channel_type == "PUSH":
                self.web_push_sender.send(db=self.db, user=user, title=title, body=body, tracking_url=tracking_url)
            else:
                return DispatchResult(status="failed", failure_reason=f"Unsupported channel {dispatch.channel_type}")
        except Exception as exc:  # pragma: no cover - external integrations
            logger.exception("Dispatch failed: %s", exc)
            return DispatchResult(status="failed", failure_reason=str(exc))

        dispatch.status = "sent"
        dispatch.sent_at = datetime.now(timezone.utc)
        self.db.add(dispatch)
        return DispatchResult(status="sent")
