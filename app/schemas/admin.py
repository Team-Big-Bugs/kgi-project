from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class NotificationTemplateCreate(BaseModel):
    trigger_type: Literal["bio_rhythm_peak", "streak_warning", "spaced_repetition_due"]
    channel_type: Literal["PUSH", "EMAIL", "LINE"]
    title_template: str
    message_body_string: Annotated[str, Field(validation_alias=AliasChoices("message_body_string", "body_template"))]
    is_active: bool = True


class NotificationTemplateUpdate(BaseModel):
    trigger_type: Literal["bio_rhythm_peak", "streak_warning", "spaced_repetition_due"] | None = None
    channel_type: Literal["PUSH", "EMAIL", "LINE"] | None = None
    title_template: str | None = None
    message_body_string: Annotated[str | None, Field(
        default=None,
        validation_alias=AliasChoices("message_body_string", "body_template"),
    )]
    is_active: bool | None = None


class NotificationTemplateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_id: int
    trigger_type: str
    channel_type: str
    title_template: str
    message_body_string: str
    is_active: bool


class ManualNotificationRequest(BaseModel):
    agent_id: int | None = None
    user_id: int | None = None
    assignment_id: int
    template_id: int | None = None

    @model_validator(mode="after")
    def normalize_agent_id(self) -> "ManualNotificationRequest":
        if self.agent_id is None:
            self.agent_id = self.user_id
        if self.agent_id is None:
            raise ValueError("agent_id is required")
        return self


class SchedulerRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    considered: int
    queued: int
    sent: int
    failed: int
    skipped_opt_out: int
    skipped_dnd: int
    skipped_duplicate: int


class AdminDashboardResponse(BaseModel):
    users: int
    templates: int
    assignments: int
    queued_dispatches: int
    sent_dispatches: int
    failed_dispatches: int


class AgentAdminSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
    line_user_id: str | None = None
    is_active: bool


class DispatchLogSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dispatch_id: int
    agent_id: int
    learning_assignment_id: int
    template_id: int
    channel_type: str
    scheduled_dispatch_time: datetime
    status: str
    tracking_token: str
    sent_at: datetime | None = None
    opened_timestamp: datetime | None = None
    failure_reason: str | None = None
