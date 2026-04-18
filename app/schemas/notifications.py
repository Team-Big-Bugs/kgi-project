from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PushSubscriptionKeys(BaseModel):
    p256dh: str | None = None
    auth: str | None = None


class PushPublicKeyResponse(BaseModel):
    public_key: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys | None = None
    p256dh_key: str | None = Field(default=None, alias="p256dhKey")
    auth_key: str | None = Field(default=None, alias="authKey")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def ensure_keys(self) -> "PushSubscriptionCreate":
        if self.p256dh_key and self.auth_key:
            return self
        if self.keys and self.keys.p256dh and self.keys.auth:
            self.p256dh_key = self.keys.p256dh
            self.auth_key = self.keys.auth
            return self
        raise ValueError("Push subscription keys are required")


class PushSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    endpoint: str
    p256dh_key: str
    auth_key: str
    is_active: bool


class PushUnsubscribeRequest(BaseModel):
    endpoint: str
