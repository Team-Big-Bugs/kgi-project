from __future__ import annotations

import base64
import hashlib
import hmac
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.db.models  # noqa: F401
from app.api.routes import admin as admin_routes
from app.api.routes import webhooks as webhooks_routes
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.agent_preference import AgentPreference
from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.line_link_request import LineLinkRequest
from app.db.models.notification_template import NotificationTemplate
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.schemas.admin import SchedulerRunResponse
from app.services.dispatch import DispatchResult
from app.services.line_link_service import generate_link_code
from app.services.scheduler import SchedulerStats
from app.services.channels import line as line_channel_module
from app.services.channels import web_push as web_push_module


settings = get_settings()


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

        self.app = create_app()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self.tmpdir.cleanup()

    def create_user(self, *, email: str, password: str, role: str, name: str) -> User:
        with self.SessionLocal() as db:
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                name=name,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    def create_preference(
        self,
        *,
        agent_id: int,
        preferred_channel: str = "EMAIL",
        peak_learning_time: str = "09:00",
        dnd_start_time: str | None = "20:00",
        dnd_end_time: str | None = "07:00",
        is_opted_out: bool = False,
    ) -> AgentPreference:
        with self.SessionLocal() as db:
            preference = AgentPreference(
                agent_id=agent_id,
                preferred_channel=preferred_channel,
                peak_learning_time=datetime.strptime(peak_learning_time, "%H:%M").time(),
                dnd_start_time=None if dnd_start_time is None else datetime.strptime(dnd_start_time, "%H:%M").time(),
                dnd_end_time=None if dnd_end_time is None else datetime.strptime(dnd_end_time, "%H:%M").time(),
                is_opted_out=is_opted_out,
            )
            db.add(preference)
            db.commit()
            db.refresh(preference)
            return preference

    def create_assignment(
        self,
        *,
        user_id: int,
        module_title: str,
        task_type: str = "mandatory_module",
        due_at: datetime | None = None,
    ) -> LearningAssignment:
        with self.SessionLocal() as db:
            assignment = LearningAssignment(
                user_id=user_id,
                module_title=module_title,
                task_type=task_type,
                due_at=due_at or datetime.now(timezone.utc) - timedelta(minutes=1),
            )
            db.add(assignment)
            db.commit()
            db.refresh(assignment)
            return assignment

    def create_template(
        self,
        *,
        trigger_type: str = "bio_rhythm_peak",
        channel_type: str = "EMAIL",
        title_template: str = "Hi {{agent_name}}",
        message_body_string: str = "Module: {{module_title}}",
        is_active: bool = True,
    ) -> NotificationTemplate:
        with self.SessionLocal() as db:
            template = NotificationTemplate(
                trigger_type=trigger_type,
                channel_type=channel_type,
                title_template=title_template,
                message_body_string=message_body_string,
                is_active=is_active,
            )
            db.add(template)
            db.commit()
            db.refresh(template)
            return template

    def create_dispatch(
        self,
        *,
        agent_id: int,
        assignment_id: int,
        template_id: int,
        tracking_token: str = "token-123",
        status: str = "sent",
    ) -> DispatchLog:
        with self.SessionLocal() as db:
            dispatch = DispatchLog(
                agent_id=agent_id,
                learning_assignment_id=assignment_id,
                template_id=template_id,
                channel_type="EMAIL",
                scheduled_dispatch_time=datetime.now(timezone.utc),
                status=status,
                tracking_token=tracking_token,
                dedupe_key=f"dedupe-{tracking_token}",
            )
            db.add(dispatch)
            db.commit()
            db.refresh(dispatch)
            return dispatch


class AuthRoutesTest(RouteTestCase):
    def test_login_sets_session_and_exposes_dashboard(self):
        agent = self.create_user(
            email=str(settings.demo_agent_email),
            password=str(settings.demo_agent_password),
            role="agent",
            name="Lin Agent",
        )

        response = self.client.post(
            "/auth/login",
            json={"email": agent.email, "password": settings.demo_agent_password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect_to"], "/dashboard")
        self.assertEqual(response.json()["user"]["email"], agent.email)

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("text/html", dashboard.headers["content-type"])
        self.assertIn("Dashboard", dashboard.text)

        me = self.client.get("/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], agent.email)

    def test_invalid_login_is_rejected(self):
        self.create_user(
            email="agent@example.com",
            password="secret123",
            role="agent",
            name="Agent",
        )

        response = self.client.post(
            "/auth/login",
            json={"email": "agent@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)


class WebPushConfigTest(unittest.TestCase):
    def test_resolve_vapid_private_key_accepts_pem_content(self):
        pem_value = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg9PK8TU5v/KdtGL8W
AWrZ7XtQP/aqmw+louTNFzlnmQShRANCAAQ//xNYMxWny4o4/FrC2uoORdbZ/WLp
rOcvN6/oqLnbpPOajjznmhTyJn7xfJct1OsxSCbdF5nOcDaJK6bJAgMn
-----END PRIVATE KEY-----"""

        resolved = web_push_module._resolve_vapid_private_key(pem_value)

        self.assertIsInstance(resolved, web_push_module.Vapid01)


class SchedulerAndAdminRoutesTest(RouteTestCase):
    def test_manual_scheduler_route_returns_stats(self):
        admin = self.create_user(email="admin@example.com", password="secret123", role="admin", name="Admin")
        self.client.post("/auth/login", json={"email": admin.email, "password": "secret123"})

        with patch.object(
            admin_routes,
            "run_scheduler",
            return_value=SchedulerStats(considered=2, queued=1, sent=1, failed=0, skipped_opt_out=0, skipped_dnd=0, skipped_duplicate=0),
        ):
            response = self.client.post("/admin/run-scheduler")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stats"], SchedulerRunResponse(
            considered=2,
            queued=1,
            sent=1,
            failed=0,
            skipped_opt_out=0,
            skipped_dnd=0,
            skipped_duplicate=0,
        ).model_dump(mode="json"))

    def test_manual_notification_creates_dispatch_and_marks_sent(self):
        admin = self.create_user(email="admin2@example.com", password="secret123", role="admin", name="Admin")
        self.client.post("/auth/login", json={"email": admin.email, "password": "secret123"})

        agent = self.create_user(email="agent2@example.com", password="secret123", role="agent", name="Lin Agent")
        self.create_preference(agent_id=agent.id, preferred_channel="EMAIL")
        assignment = self.create_assignment(user_id=agent.id, module_title="Travel Insurance")
        self.create_template(channel_type="EMAIL", trigger_type="bio_rhythm_peak")

        with patch.object(admin_routes.DispatchOrchestrator, "send_dispatch", return_value=DispatchResult(status="sent")):
            response = self.client.post(
                "/admin/test-notification",
                json={"agent_id": agent.id, "assignment_id": assignment.id},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dispatch"]["status"], "sent")

        with self.SessionLocal() as db:
            dispatch = db.scalar(select(DispatchLog).where(DispatchLog.agent_id == agent.id))
            self.assertIsNotNone(dispatch)
            self.assertEqual(dispatch.status, "sent")
            self.assertIsNotNone(dispatch.tracking_token)


class TrackingAndWebhookRoutesTest(RouteTestCase):
    def test_preferences_page_handles_naive_line_link_expiry(self):
        user = self.create_user(email="prefs@example.com", password="secret123", role="agent", name="Prefs User")
        self.create_preference(agent_id=user.id, preferred_channel="LINE")

        self.client.post("/auth/login", json={"email": user.email, "password": "secret123"})

        with self.SessionLocal() as db:
            link_request = generate_link_code(db, user=user)
            link_request.expires_at = link_request.expires_at.replace(tzinfo=None)
            db.add(link_request)
            db.commit()

        response = self.client.get("/preferences")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Preference Center", response.text)

    def test_tracking_marks_dispatch_opened_and_redirects(self):
        user = self.create_user(email="track@example.com", password="secret123", role="agent", name="Track User")
        assignment = self.create_assignment(user_id=user.id, module_title="Compliance")
        template = self.create_template(channel_type="EMAIL")
        dispatch = self.create_dispatch(
            agent_id=user.id,
            assignment_id=assignment.id,
            template_id=template.template_id,
            tracking_token="track-token-1",
            status="sent",
        )

        response = self.client.get("/track/track-token-1", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], f"/assignments/{assignment.id}")

        with self.SessionLocal() as db:
            refreshed = db.get(DispatchLog, dispatch.dispatch_id)
            self.assertIsNotNone(refreshed.opened_timestamp)

    def test_line_webhook_links_user_from_link_code(self):
        user = self.create_user(email="line@example.com", password="secret123", role="agent", name="Line User")
        with self.SessionLocal() as db:
            link_request = generate_link_code(db, user=user)
            db.refresh(link_request)
            link_code = link_request.link_code

        secret = "test-line-secret"

        payload = {
            "events": [
                {
                    "type": "message",
                    "source": {"userId": "U123456789"},
                    "message": {"type": "text", "text": f"please link {link_code}"},
                }
            ]
        }
        body = json.dumps(payload).encode("utf-8")
        signature = base64.b64encode(hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()).decode("utf-8")

        with patch.object(
            line_channel_module,
            "get_settings",
            return_value=SimpleNamespace(line_channel_secret=secret),
        ):
            response = self.client.post(
                "/line/webhook",
                content=body,
                headers={"Content-Type": "application/json", "X-Line-Signature": signature},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["linked"], 1)

        with self.SessionLocal() as db:
            refreshed_user = db.get(User, user.id)
            refreshed_request = db.scalar(select(LineLinkRequest).where(LineLinkRequest.link_code == link_code))
            self.assertEqual(refreshed_user.line_user_id, "U123456789")
            self.assertEqual(refreshed_request.status, "linked")

    def test_line_status_endpoint_reports_linked_user(self):
        user = self.create_user(email="line-status@example.com", password="secret123", role="agent", name="Line Status")
        with self.SessionLocal() as db:
            link_request = generate_link_code(db, user=user)
            db.refresh(link_request)
            refreshed_user = db.get(User, user.id)
            refreshed_user.line_user_id = "U123456789ABCDE"
            link_request.status = "linked"
            link_request.consumed_at = datetime.now(timezone.utc)
            db.add_all([refreshed_user, link_request])
            db.commit()

        self.client.post("/auth/login", json={"email": user.email, "password": "secret123"})

        response = self.client.get("/preferences/line/status")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["linked"])
        self.assertEqual(response.json()["line_status"], "Linked")
        self.assertEqual(response.json()["masked_line_user_id"], "U12345...BCDE")


class PreferencesAndPushRoutesTest(RouteTestCase):
    def test_preferences_save_redirects_with_success_flag(self):
        user = self.create_user(email="prefs-save@example.com", password="secret123", role="agent", name="Prefs Save")
        self.client.post("/auth/login", json={"email": user.email, "password": "secret123"})

        response = self.client.post(
            "/preferences",
            data={
                "preferred_channel": "PUSH",
                "dnd_start_time": "22:00",
                "dnd_end_time": "06:00",
                "peak_learning_time": "08:45",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/preferences?saved=1")

    def test_push_test_route_dispatches_web_push(self):
        user = self.create_user(email="push@example.com", password="secret123", role="agent", name="Push User")
        self.client.post("/auth/login", json={"email": user.email, "password": "secret123"})

        with patch.object(web_push_module.WebPushSender, "send", return_value=None) as mocked_send:
            response = self.client.post("/notifications/push/test")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        mocked_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
