from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urljoin

from app.core.config import get_settings, normalize_base_url
from app.core.logging import get_logger
from app.db.models.user import User


logger = get_logger(__name__)


class EmailSender:
    def send(self, *, user: User, title: str, body: str, tracking_url: str) -> None:
        settings = get_settings()
        if not user.email:
            raise ValueError("User email is missing")
        if not settings.smtp_host or not settings.smtp_from_email:
            raise RuntimeError("SMTP is not configured")
        if bool(settings.smtp_user) != bool(settings.smtp_password):
            raise RuntimeError("SMTP credentials must include both user and password")

        message = EmailMessage()
        message["Subject"] = title.strip() or settings.app_name
        message["From"] = formataddr((settings.app_name, str(settings.smtp_from_email)))
        message["To"] = user.email.strip()
        message.set_content(f"{body.strip()}\n\nOpen your module: {self._build_tracking_link(settings.app_base_url, tracking_url)}")

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.ehlo()
                if settings.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                refused = smtp.send_message(message)
                if refused:
                    raise RuntimeError(f"SMTP refused recipients: {refused}")
        except (OSError, smtplib.SMTPException) as exc:
            logger.exception("SMTP dispatch failed for user_id=%s", user.id)
            raise RuntimeError(f"SMTP dispatch failed: {exc}") from exc

    @staticmethod
    def _build_tracking_link(app_base_url: str, tracking_url: str) -> str:
        return urljoin(f"{normalize_base_url(app_base_url)}/", tracking_url.lstrip("/"))
