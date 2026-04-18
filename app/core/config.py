from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "Smart Nudge"
    app_base_url: str = "http://127.0.0.1:8000"
    secret_key: str = "change-me"
    session_cookie_name: str = "smart_nudge_session"
    cron_secret: str = "change-me"
    database_url: str = "sqlite:///./dev.db"
    timezone: str = "Asia/Taipei"

    demo_admin_email: EmailStr = "admin@smartnudge.example"
    demo_admin_password: str = "admin1234"
    demo_agent_email: EmailStr = "lin.agent@smartnudge.example"
    demo_agent_password: str = "agent1234"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: EmailStr | None = None
    smtp_use_tls: bool = True

    vapid_subject: str = "mailto:team@example.com"
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None

    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None
    line_official_account_url: str = "https://line.me/R/ti/p/@your-account"
    line_official_account_qr_url: str | None = None

    default_peak_learning_time: str = "09:00"
    default_dnd_start_time: str = "20:00"
    default_dnd_end_time: str = "07:00"
    tracking_redirect_fallback: str = "/dashboard"
    test_notification_cooldown_minutes: int = 5
    scheduler_lookback_minutes: int = 5
    nudge_lead_minutes: int = 15
    link_code_expiry_minutes: int = 20
    seed_now_offset_minutes: int = 10

    @field_validator(
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "smtp_from_email",
        "vapid_public_key",
        "vapid_private_key",
        "line_channel_secret",
        "line_channel_access_token",
        "line_official_account_qr_url",
        mode="before",
    )
    @classmethod
    def blank_strings_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
