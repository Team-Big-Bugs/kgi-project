from __future__ import annotations

import base64
import hashlib
import hmac

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.user import User


logger = get_logger(__name__)


class LineSender:
    api_url = "https://api.line.me/v2/bot/message/push"

    def send(self, *, user: User, title: str, body: str, tracking_url: str) -> None:
        settings = get_settings()
        if not settings.line_channel_access_token:
            raise RuntimeError("LINE access token is not configured")
        if not user.line_user_id:
            raise ValueError("User LINE account is not linked")

        message_text = self._build_message_text(
            title=title,
            body=body,
            tracking_url=tracking_url,
            app_base_url=settings.app_base_url,
        )
        headers = {
            "Authorization": f"Bearer {settings.line_channel_access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": user.line_user_id,
            "messages": [{"type": "text", "text": message_text[:5000]}],
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._format_http_error(exc.response)
            logger.exception("LINE dispatch rejected for user_id=%s", user.id)
            raise RuntimeError(f"LINE dispatch failed: {detail}") from exc
        except httpx.RequestError as exc:  # pragma: no cover - external integration failure
            logger.exception("LINE dispatch request error for user_id=%s", user.id)
            raise RuntimeError(f"LINE dispatch failed: {exc}") from exc

    @staticmethod
    def _build_message_text(*, title: str, body: str, tracking_url: str, app_base_url: str) -> str:
        base_url = app_base_url.rstrip("/")
        suffix = tracking_url if tracking_url.startswith("/") else f"/{tracking_url}"
        return f"{title.strip()}\n{body.strip()}\n\nOpen: {base_url}{suffix}"

    @staticmethod
    def _format_http_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        return f"HTTP {response.status_code}: {payload}"


def verify_line_signature(body: bytes, signature: str | None) -> bool:
    settings = get_settings()
    signature_value = signature.strip() if signature else None
    if not settings.line_channel_secret or not signature_value:
        return False
    digest = hmac.new(settings.line_channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature_value)
