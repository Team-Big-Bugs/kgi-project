from __future__ import annotations

from pydantic import BaseModel


class LineWebhookResponse(BaseModel):
    processed: int
    linked: int
    ignored: int
