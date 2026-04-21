from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes._common import expects_html, parse_bool, render_or_json, require_admin_user
from app.db.models.agent_preference import AgentPreference
from app.db.models.dispatch_log import DispatchLog
from app.db.models.learning_assignment import LearningAssignment
from app.db.models.notification_template import NotificationTemplate
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.admin import (
    AdminDashboardResponse,
    DispatchLogSummary,
    ManualNotificationRequest,
    NotificationTemplateCreate,
    NotificationTemplateSummary,
    NotificationTemplateUpdate,
    SchedulerRunResponse,
)
from app.services.dispatch import DispatchOrchestrator
from app.services.scheduler import run_scheduler


router = APIRouter(prefix="/admin", tags=["admin"])


def _summary(db: Session) -> AdminDashboardResponse:
    return AdminDashboardResponse(
        users=db.scalar(select(func.count(User.id)).where(User.role == "agent")) or 0,
        templates=db.scalar(select(func.count(NotificationTemplate.template_id))) or 0,
        assignments=db.scalar(select(func.count(LearningAssignment.id))) or 0,
        queued_dispatches=db.scalar(select(func.count(DispatchLog.dispatch_id)).where(DispatchLog.status == "queued")) or 0,
        sent_dispatches=db.scalar(select(func.count(DispatchLog.dispatch_id)).where(DispatchLog.status == "sent")) or 0,
        failed_dispatches=db.scalar(select(func.count(DispatchLog.dispatch_id)).where(DispatchLog.status == "failed")) or 0,
    )


def _template_payload(template: NotificationTemplate) -> dict:
    return NotificationTemplateSummary.model_validate(template).model_dump(mode="json")


def _agent_payloads(db: Session) -> list[dict]:
    agents = list(db.scalars(select(User).where(User.role == "agent").order_by(User.name.asc())))
    preferences = {pref.agent_id: pref for pref in db.scalars(select(AgentPreference))}
    payload = []
    for agent in agents:
        preference = preferences.get(agent.id)
        payload.append(
            {
                "id": agent.id,
                "name": agent.name,
                "email": agent.email,
                "role": agent.role,
                "line_user_id": agent.line_user_id,
                "is_active": agent.is_active,
                "channel": preference.preferred_channel if preference else "EMAIL",
                "badge_tone": "primary" if preference and preference.preferred_channel == "LINE" else "soft",
                "link_state": "linked" if agent.line_user_id else "not linked",
                "opt_out_state": "opted out" if preference and preference.is_opted_out else "active",
            }
        )
    return payload


def _dispatch_payloads(db: Session) -> list[dict]:
    dispatches = list(db.scalars(select(DispatchLog).order_by(DispatchLog.scheduled_dispatch_time.desc()).limit(50)))
    user_map = {user.id: user.name for user in db.scalars(select(User))}
    template_map = {template.template_id: template.title_template for template in db.scalars(select(NotificationTemplate))}
    payload = []
    for dispatch in dispatches:
        payload.append(
            {
                **DispatchLogSummary.model_validate(dispatch).model_dump(mode="json"),
                "agent_name": user_map.get(dispatch.agent_id, f"Agent #{dispatch.agent_id}"),
                "template_name": template_map.get(dispatch.template_id, f"Template #{dispatch.template_id}"),
                "channel": dispatch.channel_type,
                "status_tone": "success" if dispatch.status == "sent" else "warning" if dispatch.status == "queued" else "error",
            }
        )
    return payload


def _assignment_payloads(db: Session) -> list[dict]:
    assignments = list(db.scalars(select(LearningAssignment).order_by(LearningAssignment.due_at.desc()).limit(50)))
    user_map = {user.id: user.name for user in db.scalars(select(User))}
    return [
        {
            "id": assignment.id,
            "module_title": assignment.module_title,
            "task_type": assignment.task_type,
            "status": "completed" if assignment.completed_at else "pending",
            "due_at": assignment.due_at,
            "agent_name": user_map.get(assignment.user_id, f"Agent #{assignment.user_id}"),
        }
        for assignment in assignments
    ]


def _conversion_payloads(db: Session) -> list[dict]:
    dispatches = list(
        db.scalars(
            select(DispatchLog)
            .where(DispatchLog.opened_timestamp.is_not(None))
            .order_by(DispatchLog.opened_timestamp.desc())
            .limit(5)
        )
    )
    user_map = {user.id: user.name for user in db.scalars(select(User))}
    template_map = {template.template_id: template.title_template for template in db.scalars(select(NotificationTemplate))}
    payload = []
    for dispatch in dispatches:
        payload.append(
            {
                "dispatch_id": dispatch.dispatch_id,
                "agent_name": user_map.get(dispatch.agent_id, f"Agent #{dispatch.agent_id}"),
                "template_name": template_map.get(dispatch.template_id, f"Template #{dispatch.template_id}"),
                "channel": dispatch.channel_type,
                "opened_timestamp": dispatch.opened_timestamp,
                "scheduled_dispatch_time": dispatch.scheduled_dispatch_time,
            }
        )
    return payload


@router.get("")
@router.get("/")
@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    summary = _summary(db)
    sent_count = db.scalar(select(func.count(DispatchLog.dispatch_id)).where(DispatchLog.status == "sent")) or 0
    opened_count = db.scalar(
        select(func.count(DispatchLog.dispatch_id)).where(DispatchLog.opened_timestamp.is_not(None))
    ) or 0
    open_rate = (opened_count / sent_count * 100) if sent_count else 0
    recent_dispatch = db.scalar(select(DispatchLog).order_by(DispatchLog.scheduled_dispatch_time.desc()))
    recent_conversions = _conversion_payloads(db)
    context = {
        "page_title": "Admin Dashboard",
        "summary": summary,
        "queue_state": "Queue healthy" if summary.failed_dispatches == 0 else "Needs review",
        "env_label": "Railway + Supabase",
        "last_run_label": (
            f"Last dispatch {recent_dispatch.scheduled_dispatch_time.astimezone(timezone.utc).strftime('%H:%M UTC')}"
            if recent_dispatch
            else "No dispatches yet"
        ),
        "queued_count": str(summary.queued_dispatches),
        "sent_count": str(sent_count),
        "opened_count": str(opened_count),
        "conversion_count": str(opened_count),
        "open_rate": f"{open_rate:.0f}%",
        "conversion_summary": (
            f"{opened_count} of {sent_count} sent nudges converted to opens."
            if sent_count
            else "No sent nudges yet, so open rate is waiting for data."
        ),
        "recent_conversions": recent_conversions,
        "metrics": [
            {"label": "Agents", "value": summary.users, "note": "Seeded agents ready for demo."},
            {"label": "Templates", "value": summary.templates, "note": "Cross-channel message dictionary."},
            {"label": "Assignments", "value": summary.assignments, "note": "Mandatory modules plus recall items."},
        ],
        "templates_url": "/admin/templates",
        "dispatches_url": "/admin/dispatches",
        "scheduler_url": "/admin/scheduler",
    }
    return render_or_json(
        request,
        "admin/dashboard.html",
        context,
        {
            "page": "admin-dashboard",
            "page_title": "Admin Dashboard",
            "summary": summary.model_dump(mode="json"),
            "conversion": {
                "sent_count": sent_count,
                "opened_count": opened_count,
                "open_rate": open_rate,
                "recent_conversions": recent_conversions,
            },
        },
    )


@router.get("/agents")
def list_agents(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    agents = _agent_payloads(db)
    linked = len([agent for agent in agents if agent["line_user_id"]])
    opted_out = len([agent for agent in agents if agent["opt_out_state"] == "opted out"])
    return render_or_json(
        request,
        "admin/agents.html",
        {
            "page_title": "Agents",
            "agents": agents,
            "linked_label": f"{linked} linked",
            "unlinked_label": f"{len(agents) - linked} unlinked",
            "opt_out_label": f"{opted_out} opted out",
        },
        {"page": "admin-agents", "agents": agents},
    )


@router.get("/templates")
def list_templates(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    templates = list(db.scalars(select(NotificationTemplate).order_by(NotificationTemplate.template_id.desc())))
    payload = [_template_payload(template) for template in templates]
    return render_or_json(
        request,
        "admin/templates.html",
        {
            "page_title": "Templates",
            "templates": payload,
            "template_save_url": "/admin/templates",
            "dispatches_url": "/admin/dispatches",
        },
        {"page": "admin-templates", "templates": payload},
    )


@router.post("/templates")
async def create_template(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    if request.headers.get("content-type", "").lower().startswith("application/json"):
        payload_data = await request.json()
    else:
        form = await request.form()
        payload_data = {
            "trigger_type": form.get("trigger_type", "bio_rhythm_peak"),
            "channel_type": form.get("channel_type", "EMAIL"),
            "title_template": form.get("title_template", ""),
            "message_body_string": form.get("message_body_string") or form.get("body_template", ""),
            "is_active": parse_bool(form.get("is_active", True)),
        }

    try:
        payload = NotificationTemplateCreate.model_validate(payload_data)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    template = NotificationTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    if expects_html(request):
        return RedirectResponse(url="/admin/templates", status_code=status.HTTP_303_SEE_OTHER)
    return {"ok": True, "template": _template_payload(template)}


@router.put("/templates/{template_id}")
def update_template(template_id: int, payload: NotificationTemplateUpdate, request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    template = db.get(NotificationTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"ok": True, "template": _template_payload(template)}


@router.get("/dispatches")
def list_dispatches(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    dispatches = _dispatch_payloads(db)
    return render_or_json(
        request,
        "admin/dispatches.html",
        {
            "page_title": "Dispatches",
            "dispatches": dispatches,
            "queue_count": f"{len([item for item in dispatches if item['status'] == 'queued'])} queued",
            "sent_count": f"{len([item for item in dispatches if item['status'] == 'sent'])} sent",
            "failed_count": f"{len([item for item in dispatches if item['status'] == 'failed'])} failed",
            "scheduler_url": "/admin/scheduler",
            "test_url": "/admin/test-notification",
        },
        {"page": "admin-dispatches", "dispatches": dispatches},
    )


@router.get("/assignments")
def list_assignments(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    assignments = _assignment_payloads(db)
    return render_or_json(
        request,
        "admin/assignments.html",
        {"page_title": "Assignments", "assignments": assignments},
        {"page": "admin-assignments", "assignments": assignments},
    )


@router.get("/scheduler")
def scheduler_page(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    dispatches = list(db.scalars(select(DispatchLog).order_by(DispatchLog.scheduled_dispatch_time.desc()).limit(5)))
    last_runs = [
        {
            "label": f"{dispatch.channel_type} {dispatch.status}",
            "time": dispatch.scheduled_dispatch_time,
            "note": dispatch.failure_reason or "Dispatch log available.",
        }
        for dispatch in dispatches
    ]
    return render_or_json(
        request,
        "admin/scheduler.html",
        {
            "page_title": "Scheduler",
            "last_runs": last_runs,
            "cron_state": "Healthy",
            "runtime_label": "Railway Cron",
            "dispatches_url": "/admin/dispatches",
        },
        {"page": "admin-scheduler", "last_runs": last_runs},
    )


@router.post("/test-notification")
def test_notification(payload: ManualNotificationRequest, request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    user = db.get(User, payload.agent_id)
    assignment = db.get(LearningAssignment, payload.assignment_id)
    if user is None or assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User or assignment not found")

    preference = db.scalar(select(AgentPreference).where(AgentPreference.agent_id == user.id))
    if preference is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User preference is missing")

    if payload.template_id is not None:
        template = db.get(NotificationTemplate, payload.template_id)
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    else:
        trigger_type = "spaced_repetition_due" if assignment.task_type == "memory_recall" else "bio_rhythm_peak"
        template = db.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.trigger_type == trigger_type,
                NotificationTemplate.channel_type == preference.preferred_channel,
                NotificationTemplate.is_active.is_(True),
            )
        )
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matching template not found")

    orchestrator = DispatchOrchestrator(db)
    scheduled_dispatch_time = datetime.now(timezone.utc)
    dedupe_key = f"manual:{user.id}:{assignment.id}:{template.template_id}:{scheduled_dispatch_time.isoformat()}"
    dispatch = orchestrator.create_dispatch_log(
        user=user,
        preference=preference,
        assignment=assignment,
        template=template,
        scheduled_dispatch_time=scheduled_dispatch_time,
        dedupe_key=dedupe_key,
    )
    result = orchestrator.send_dispatch(dispatch)
    dispatch.status = result.status
    dispatch.failure_reason = result.failure_reason
    if result.status == "sent" and dispatch.sent_at is None:
        dispatch.sent_at = datetime.now(timezone.utc)
    db.add(dispatch)
    db.commit()
    db.refresh(dispatch)
    return {"ok": True, "dispatch": DispatchLogSummary.model_validate(dispatch).model_dump(mode="json")}


@router.post("/run-scheduler")
def run_scheduler_manually(request: Request, db: Session = Depends(get_db)):
    require_admin_user(request, db)
    stats = run_scheduler(db)
    return {"ok": True, "stats": SchedulerRunResponse.model_validate(stats).model_dump(mode="json")}
