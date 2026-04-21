from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.routes._common import (
    expects_html,
    format_time_value,
    parse_bool,
    parse_time_value,
    preference_payload,
    render_or_json,
    require_user,
)
from app.core.config import get_settings
from app.db.models.agent_preference import AgentPreference
from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.line_link_request import LineLinkRequest
from app.db.models.web_push_subscription import WebPushSubscription
from app.db.session import get_db
from app.schemas.agent import LineLinkStartResponse, PreferenceUpdate
from app.services.line_link_service import build_qr_data_uri, generate_link_code


settings = get_settings()
router = APIRouter(tags=["agent"])


def _user_assignments(db: Session, user_id: int, *, pending_only: bool = False) -> list[LearningAssignment]:
    stmt = select(LearningAssignment).where(LearningAssignment.user_id == user_id)
    if pending_only:
        stmt = stmt.where(LearningAssignment.completed_at.is_(None))
    stmt = stmt.order_by(desc(LearningAssignment.due_at), desc(LearningAssignment.id))
    return list(db.scalars(stmt))


def _serialize_assignments(assignments: list[LearningAssignment]) -> list[dict]:
    return [
        {
            "id": assignment.id,
            "module_title": assignment.module_title,
            "task_type": assignment.task_type,
            "due_at": assignment.due_at,
            "completed_at": assignment.completed_at,
            "status": "completed" if assignment.completed_at else "pending",
            "detail_url": f"/assignments/{assignment.id}",
        }
        for assignment in assignments
    ]


def _user_dispatches(db: Session, user_id: int) -> list[DispatchLog]:
    stmt = select(DispatchLog).where(DispatchLog.agent_id == user_id).order_by(desc(DispatchLog.scheduled_dispatch_time))
    return list(db.scalars(stmt))


def _serialize_dispatches(dispatches: list[DispatchLog]) -> list[dict]:
    return [
        {
            "dispatch_id": dispatch.dispatch_id,
            "status": dispatch.status,
            "channel_type": dispatch.channel_type,
            "tracking_token": dispatch.tracking_token,
            "sent_at": dispatch.sent_at,
            "opened_timestamp": dispatch.opened_timestamp,
            "failure_reason": dispatch.failure_reason,
        }
        for dispatch in dispatches
    ]


def _latest_link_request(db: Session, user_id: int) -> LineLinkRequest | None:
    return db.scalar(
        select(LineLinkRequest).where(LineLinkRequest.user_id == user_id).order_by(desc(LineLinkRequest.created_at))
    )


def _active_link_request(db: Session, user_id: int) -> LineLinkRequest | None:
    link_request = _latest_link_request(db, user_id)
    if link_request and link_request.status == "pending":
        expires_at = link_request.expires_at
        compare_now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            compare_now = datetime.utcnow()
        if expires_at > compare_now:
            return link_request
    return None


def _mask_line_user_id(line_user_id: str | None) -> str | None:
    if not line_user_id:
        return None
    if len(line_user_id) <= 10:
        return line_user_id
    return f"{line_user_id[:6]}...{line_user_id[-4:]}"


def _line_link_state(db: Session, user_id: int, line_user_id: str | None) -> dict:
    latest_request = _latest_link_request(db, user_id)
    active_request = _active_link_request(db, user_id)
    linked = bool(line_user_id)
    linked_at = None
    if latest_request and latest_request.status == "linked":
        linked_at = latest_request.consumed_at or latest_request.updated_at

    return {
        "line_connected": linked,
        "line_status": "Linked" if linked else "Not linked",
        "line_status_tone": "success" if linked else "neutral",
        "line_masked_user_id": _mask_line_user_id(line_user_id),
        "line_linked_at": linked_at,
        "line_active_request": active_request,
        "line_latest_request": latest_request,
    }


def _dashboard_context(user, preference: AgentPreference | None, assignments: list[LearningAssignment], dispatches: list[DispatchLog]) -> dict:
    next_assignment = assignments[0] if assignments else None
    peak_window = format_time_value(preference.peak_learning_time) if preference else settings.default_peak_learning_time
    preferred_channel = preference.preferred_channel if preference else "EMAIL"
    return {
        "page_title": "Agent Dashboard",
        "page_subtitle": "Your next learning nudge is timed for the right window.",
        "agent_name": user.name,
        "module_title": next_assignment.module_title if next_assignment else "Travel Insurance Essentials",
        "peak_window": peak_window,
        "next_peak_window": f"Peak window {peak_window}",
        "preferred_channel": preferred_channel,
        "channel_label": f"{preferred_channel} ready",
        "due_count": str(len([item for item in assignments if item.completed_at is None])),
        "due_today_label": f"{len([item for item in assignments if item.completed_at is None])} due today",
        "assignments": _serialize_assignments(assignments),
        "dispatches": _serialize_dispatches(dispatches),
        "upcoming_nudges": [
            {
                "title": f"{dispatch.channel_type} reminder",
                "scheduled_at": dispatch.scheduled_dispatch_time,
                "description": dispatch.failure_reason or "Queued from the scheduler.",
                "channel": dispatch.channel_type,
                "status": dispatch.status.title(),
            }
            for dispatch in dispatches[:3]
        ],
        "preferences_url": "/preferences",
        "assignments_url": "/assignments",
        "history_url": "/history",
        "assignment_url": f"/assignments/{next_assignment.id}" if next_assignment else "/assignments",
        "line_connect_url": "/preferences/line/connect",
    }


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    preference = db.scalar(select(AgentPreference).where(AgentPreference.agent_id == user.id))
    assignments = _user_assignments(db, user.id, pending_only=True)
    dispatches = _user_dispatches(db, user.id)
    context = _dashboard_context(user, preference, assignments, dispatches)

    return render_or_json(
        request,
        "agent/dashboard.html",
        context,
        {
            "page": "dashboard",
            "page_title": context["page_title"],
            "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
            "preference": preference_payload(preference),
            "assignments": context["assignments"],
            "dispatches": context["dispatches"],
        },
    )


@router.get("/preferences")
def preferences(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    preference = db.scalar(select(AgentPreference).where(AgentPreference.agent_id == user.id))
    active_push = db.scalar(
        select(WebPushSubscription).where(
            WebPushSubscription.user_id == user.id,
            WebPushSubscription.is_active.is_(True),
        )
    )
    line_state = _line_link_state(db, user.id, user.line_user_id)
    active_request = line_state["line_active_request"]
    pending_assignments = _user_assignments(db, user.id, pending_only=True)
    line_qr = None
    if active_request is not None and not line_state["line_connected"]:
        line_qr = build_qr_data_uri(settings.line_official_account_qr_url or settings.line_official_account_url)

    context = {
        "page_title": "Preference Center",
        "saved": request.query_params.get("saved") == "1",
        "user": user,
        "preferred_channel": preference.preferred_channel if preference else "EMAIL",
        "dnd_label": (
            f"Do not disturb {format_time_value(preference.dnd_start_time)} - {format_time_value(preference.dnd_end_time)}"
            if preference and preference.dnd_start_time and preference.dnd_end_time
            else f"Do not disturb after {settings.default_dnd_start_time}"
        ),
        "opt_out_label": (
            "Opted out for compliance"
            if preference and preference.is_opted_out
            else "Nudges active"
        ),
        "dnd_start_time": format_time_value(preference.dnd_start_time) if preference else settings.default_dnd_start_time,
        "dnd_end_time": format_time_value(preference.dnd_end_time) if preference else settings.default_dnd_end_time,
        "is_opted_out": preference.is_opted_out if preference else False,
        "peak_learning_time": format_time_value(preference.peak_learning_time) if preference else settings.default_peak_learning_time,
        "line_status": line_state["line_status"],
        "line_status_tone": line_state["line_status_tone"],
        "line_connected": line_state["line_connected"],
        "line_masked_user_id": line_state["line_masked_user_id"],
        "line_linked_at": line_state["line_linked_at"],
        "push_status_text": "Connected" if active_push else "Not connected",
        "push_status_tone": "success" if active_push else "neutral",
        "agent_name": user.name,
        "module_title": pending_assignments[0].module_title if pending_assignments else "Travel Insurance Essentials",
        "line_link_code": active_request.link_code if active_request else "",
        "line_link_refresh_url": "/preferences/line/link/start",
        "line_connect_url": "/preferences/line/connect",
        "line_status_url": "/preferences/line/status",
        "line_qr_data_uri": line_qr,
        "vapid_public_key_url": "/notifications/push/public-key",
        "push_subscribe_url": "/notifications/push/subscribe",
        "push_test_url": "/notifications/push/test",
        "push_local_test_label": "Show local notification",
        "dashboard_url": "/dashboard",
        "preferred_channel_label": preference.preferred_channel if preference else "Email",
    }

    return render_or_json(
        request,
        "agent/preferences.html",
        context,
        {
            "page": "preferences",
            "page_title": "Preferences",
            "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
            "preference": preference_payload(preference),
            "line": {
                "official_account_url": settings.line_official_account_url,
                "active_request": None
                if active_request is None
                else {
                    "link_code": active_request.link_code,
                    "expires_at": active_request.expires_at,
                    "status": active_request.status,
                },
            },
        },
    )


@router.post("/preferences")
@router.put("/preferences")
async def update_preferences(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if request.headers.get("content-type", "").lower().startswith("application/json"):
        payload_data = await request.json()
    else:
        form = await request.form()
        payload_data = {
            "preferred_channel": form.get("preferred_channel", "EMAIL"),
            "dnd_start_time": parse_time_value(form.get("dnd_start_time")),
            "dnd_end_time": parse_time_value(form.get("dnd_end_time")),
            "is_opted_out": parse_bool(form.get("is_opted_out")),
            "peak_learning_time": parse_time_value(form.get("peak_learning_time")) or parse_time_value(settings.default_peak_learning_time),
        }

    try:
        payload = PreferenceUpdate.model_validate(payload_data)
    except ValidationError as exc:
        if expects_html(request):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        raise

    preference = db.scalar(select(AgentPreference).where(AgentPreference.agent_id == user.id))
    if preference is None:
        preference = AgentPreference(agent_id=user.id)
    preference.preferred_channel = payload.preferred_channel
    preference.dnd_start_time = payload.dnd_start_time
    preference.dnd_end_time = payload.dnd_end_time
    preference.is_opted_out = payload.is_opted_out
    preference.peak_learning_time = payload.peak_learning_time
    db.add(preference)
    db.commit()
    db.refresh(preference)

    if expects_html(request):
        return RedirectResponse(url="/preferences?saved=1", status_code=status.HTTP_303_SEE_OTHER)
    return {"ok": True, "preference": preference_payload(preference)}


@router.get("/preferences/line/connect")
@router.get("/line/connect")
def line_connect(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    line_state = _line_link_state(db, user.id, user.line_user_id)
    active_request = line_state["line_active_request"]
    if active_request is None and not line_state["line_connected"]:
        active_request = generate_link_code(db, user=user)
        line_state = _line_link_state(db, user.id, user.line_user_id)

    qr_payload = settings.line_official_account_qr_url or settings.line_official_account_url
    context = {
        "page_title": "LINE Connection",
        "line_status": "Linked" if line_state["line_connected"] else "Awaiting link",
        "line_status_tone": "success" if line_state["line_connected"] else "accent",
        "line_connected": line_state["line_connected"],
        "line_masked_user_id": line_state["line_masked_user_id"],
        "line_linked_at": line_state["line_linked_at"],
        "webhook_status": "Webhook ready",
        "line_link_code": active_request.link_code if active_request else "",
        "line_link_refresh_url": "/preferences/line/link/start",
        "line_status_url": "/preferences/line/status",
        "qr_data_uri": build_qr_data_uri(qr_payload) if not line_state["line_connected"] else None,
        "official_account_url": settings.line_official_account_url,
        "preferences_url": "/preferences",
    }

    return render_or_json(
        request,
        "agent/line_connect.html",
        context,
        {
            "page": "line-connect",
            "page_title": "LINE Connect",
            "line": {
                "official_account_url": settings.line_official_account_url,
                "link_code": active_request.link_code,
                "expires_at": active_request.expires_at,
            },
        },
    )


@router.get("/preferences/line/status")
def line_status(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    line_state = _line_link_state(db, user.id, user.line_user_id)
    active_request = line_state["line_active_request"]

    return {
        "ok": True,
        "linked": line_state["line_connected"],
        "line_status": line_state["line_status"],
        "line_status_tone": line_state["line_status_tone"],
        "masked_line_user_id": line_state["line_masked_user_id"],
        "linked_at": line_state["line_linked_at"],
        "active_link_code": active_request.link_code if active_request else None,
    }


@router.post("/preferences/line/link/start")
def start_line_link(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    link_request = generate_link_code(db, user=user)
    qr_payload = settings.line_official_account_qr_url or settings.line_official_account_url
    response = LineLinkStartResponse(
        link_code=link_request.link_code,
        qr_data_uri=build_qr_data_uri(qr_payload),
        official_account_url=settings.line_official_account_url,
        expires_at=link_request.expires_at,
    )
    if expects_html(request):
        return RedirectResponse(url="/preferences/line/connect", status_code=status.HTTP_303_SEE_OTHER)
    response_payload = response.model_dump(mode="json")
    return {"ok": True, **response_payload, "line_link": response_payload}


@router.get("/assignments")
def assignments(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    assignments_list = _user_assignments(db, user.id)
    serialized = _serialize_assignments(assignments_list)
    return render_or_json(
        request,
        "agent/assignments.html",
        {
            "page_title": "Assignments",
            "assignments": serialized,
            "due_count": str(len([item for item in assignments_list if item.completed_at is None])),
            "completed_count": str(len([item for item in assignments_list if item.completed_at is not None])),
            "mandatory_count": str(len([item for item in assignments_list if item.task_type == "mandatory_module"])),
            "recall_count": str(len([item for item in assignments_list if item.task_type == "memory_recall"])),
        },
        {"page": "assignments", "assignments": serialized},
    )


@router.get("/assignments/{assignment_id}")
def assignment_detail(assignment_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    assignment = db.scalar(
        select(LearningAssignment).where(LearningAssignment.id == assignment_id, LearningAssignment.user_id == user.id)
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    context = {
        "page_title": "Assignment Detail",
        "assignment": assignment,
        "status_label": "Completed" if assignment.completed_at else "Pending",
        "due_at_label": assignment.due_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "back_url": "/assignments",
    }
    return render_or_json(
        request,
        "agent/assignment_detail.html",
        context,
        {
            "page": "assignment-detail",
            "assignment": {
                "id": assignment.id,
                "module_title": assignment.module_title,
                "task_type": assignment.task_type,
                "due_at": assignment.due_at,
                "completed_at": assignment.completed_at,
            },
        },
    )


@router.post("/assignments/{assignment_id}/complete")
def complete_assignment(assignment_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    assignment = db.scalar(
        select(LearningAssignment).where(LearningAssignment.id == assignment_id, LearningAssignment.user_id == user.id)
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    assignment.completed_at = assignment.completed_at or datetime.now(timezone.utc)
    db.add(assignment)
    db.commit()
    if expects_html(request):
        return RedirectResponse(url=f"/assignments/{assignment.id}", status_code=status.HTTP_303_SEE_OTHER)
    return {"ok": True, "assignment_id": assignment.id}


@router.get("/history")
def history(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    dispatches = _user_dispatches(db, user.id)
    history_items = [
        {
            "title": f"{dispatch.channel_type} reminder",
            "time": dispatch.scheduled_dispatch_time,
            "description": dispatch.failure_reason or "Tracked notification event.",
            "channel": dispatch.channel_type,
            "status": "opened" if dispatch.opened_timestamp else dispatch.status,
        }
        for dispatch in dispatches
    ]
    return render_or_json(
        request,
        "agent/history.html",
        {
            "page_title": "History",
            "history": history_items,
            "open_rate_label": f"{len([item for item in dispatches if item.opened_timestamp])} opens",
            "failed_label": f"{len([item for item in dispatches if item.status == 'failed'])} failed",
        },
        {"page": "history", "history": history_items},
    )
