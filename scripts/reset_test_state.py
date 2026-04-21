from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.line_link_request import LineLinkRequest
from app.db.models.user import User
from app.db.models.web_push_subscription import WebPushSubscription
from app.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset one agent's test state without wiping the whole database.",
    )
    parser.add_argument("--email", required=True, help="Agent email to reset.")
    parser.add_argument(
        "--all-dispatches",
        action="store_true",
        help="Delete all dispatch logs for the agent instead of only today's local dispatches.",
    )
    parser.add_argument(
        "--reset-line",
        action="store_true",
        help="Clear the stored LINE user id and delete previous LINE link requests.",
    )
    parser.add_argument(
        "--reset-push",
        action="store_true",
        help="Delete saved web push subscriptions so the browser has to subscribe again.",
    )
    parser.add_argument(
        "--reset-assignments",
        action="store_true",
        help="Mark the agent's assignments as pending again by clearing completed_at.",
    )
    return parser.parse_args()


def local_day_bounds(local_tz: ZoneInfo) -> tuple[datetime, datetime]:
    now_local = datetime.now(local_tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def main() -> None:
    args = parse_args()
    settings = get_settings()
    local_tz = ZoneInfo(settings.timezone)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is None:
            raise SystemExit(f"User not found for email={args.email}")

        deleted_dispatches = 0
        if args.all_dispatches:
            dispatches = list(db.scalars(select(DispatchLog).where(DispatchLog.agent_id == user.id)))
        else:
            start_utc, end_utc = local_day_bounds(local_tz)
            dispatches = list(
                db.scalars(
                    select(DispatchLog).where(
                        DispatchLog.agent_id == user.id,
                        DispatchLog.scheduled_dispatch_time >= start_utc,
                        DispatchLog.scheduled_dispatch_time < end_utc,
                    )
                )
            )

        for dispatch in dispatches:
            db.delete(dispatch)
            deleted_dispatches += 1

        deleted_line_requests = 0
        if args.reset_line:
            deleted_line_requests = db.query(LineLinkRequest).filter(LineLinkRequest.user_id == user.id).delete()
            user.line_user_id = None
            db.add(user)

        deleted_push_subscriptions = 0
        if args.reset_push:
            deleted_push_subscriptions = (
                db.query(WebPushSubscription).filter(WebPushSubscription.user_id == user.id).delete()
            )

        reset_assignments = 0
        if args.reset_assignments:
            assignments = list(db.scalars(select(LearningAssignment).where(LearningAssignment.user_id == user.id)))
            for assignment in assignments:
                if assignment.completed_at is not None:
                    assignment.completed_at = None
                    db.add(assignment)
                    reset_assignments += 1

        db.commit()

    reset_scope = "all dispatches" if args.all_dispatches else "today's dispatches"
    print(
        f"Reset complete for {args.email}: "
        f"deleted {deleted_dispatches} {reset_scope}, "
        f"deleted {deleted_line_requests} line link requests, "
        f"deleted {deleted_push_subscriptions} push subscriptions, "
        f"reset {reset_assignments} assignments to pending."
    )
    if args.reset_line:
        print("App-side LINE linking is cleared. If you want a true first-friend demo, also unfriend/block the OA in LINE.")


if __name__ == "__main__":
    main()
