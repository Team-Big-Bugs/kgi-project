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
    reply_api_url = "https://api.line.me/v2/bot/message/reply"

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
        payload = {
            "to": user.line_user_id,
            "messages": [{"type": "text", "text": message_text[:5000]}],
        }
        self._post_message(
            self.api_url,
            payload,
            access_token=settings.line_channel_access_token,
            user_id=user.id,
        )

    def reply_text(self, *, reply_token: str, text: str) -> None:
        settings = get_settings()
        if not settings.line_channel_access_token:
            raise RuntimeError("LINE access token is not configured")
        if not reply_token.strip():
            raise ValueError("LINE reply token is missing")

        payload = {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": text[:5000]}],
        }
        self._post_message(self.reply_api_url, payload, access_token=settings.line_channel_access_token)

    def _post_message(
        self,
        url: str,
        payload: dict,
        *,
        access_token: str,
        user_id: int | None = None,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._format_http_error(exc.response)
            if user_id is not None:
                logger.exception("LINE dispatch rejected for user_id=%s", user_id)
            else:
                logger.exception("LINE reply rejected")
            raise RuntimeError(f"LINE dispatch failed: {detail}") from exc
        except httpx.RequestError as exc:  # pragma: no cover - external integration failure
            if user_id is not None:
                logger.exception("LINE dispatch request error for user_id=%s", user_id)
            else:
                logger.exception("LINE reply request error")
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
