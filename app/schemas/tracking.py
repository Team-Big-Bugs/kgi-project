from __future__ import annotations

from pydantic import BaseModel


class TrackingResponse(BaseModel):
    tracking_token: str
    opened: bool
    redirect_to: str
