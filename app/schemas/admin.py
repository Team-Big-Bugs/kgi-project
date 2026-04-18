from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class NotificationTemplateCreate(BaseModel):
    trigger_type: Literal["bio_rhythm_peak", "streak_warning", "spaced_repetition_due"]
    channel_type: Literal["PUSH", "EMAIL", "LINE"]
    title_template: str
    body_template: str
    is_active: bool = True


class NotificationTemplateUpdate(BaseModel):
    trigger_type: Literal["bio_rhythm_peak", "streak_warning", "spaced_repetition_due"] | None = None
    channel_type: Literal["PUSH", "EMAIL", "LINE"] | None = None
    title_template: str | None = None
    body_template: str | None = None
    is_active: bool | None = None


class NotificationTemplateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trigger_type: str
    channel_type: str
    title_template: str
    body_template: str
    is_active: bool


class ManualNotificationRequest(BaseModel):
    user_id: int
    assignment_id: int
    template_id: int | None = None


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

    id: int
    user_id: int
    learning_assignment_id: int
    template_id: int
    channel_type: str
    scheduled_dispatch_time: datetime
    status: str
    tracking_token: str
    sent_at: datetime | None = None
    opened_at: datetime | None = None
    failure_reason: str | None = None
