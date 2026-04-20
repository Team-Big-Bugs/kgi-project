from __future__ import annotations

from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PreferenceUpdate(BaseModel):
    preferred_channel: Literal["PUSH", "EMAIL", "LINE"]
    dnd_start_time: time | None = None
    dnd_end_time: time | None = None
    is_opted_out: bool = False
    peak_learning_time: time


class PreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: int
    preferred_channel: str
    dnd_start_time: time | None = None
    dnd_end_time: time | None = None
    is_opted_out: bool
    peak_learning_time: time


class AssignmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_title: str
    task_type: str
    due_at: datetime
    completed_at: datetime | None = None


class DispatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dispatch_id: int
    status: str
    channel_type: str
    tracking_token: str
    sent_at: datetime | None = None
    opened_timestamp: datetime | None = None
    failure_reason: str | None = None


class DashboardResponse(BaseModel):
    user: dict
    preference: dict | None
    assignments: list[dict]
    dispatches: list[dict]


class LineLinkStartResponse(BaseModel):
    link_code: str
    qr_data_uri: str
    official_account_url: str
    expires_at: datetime
