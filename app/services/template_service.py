from __future__ import annotations

import re

from app.db.models.learning_assignment import LearningAssignment
from app.db.models.notification_template import NotificationTemplate
from app.db.models.user import User


PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


def _stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _render_template_string(template_string: str, context: dict[str, object]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        return _stringify(context[key])

    return PLACEHOLDER_PATTERN.sub(replace, template_string)


def render_template_message(
    template: NotificationTemplate,
    *,
    user: User,
    assignment: LearningAssignment,
    peak_learning_time: str,
) -> tuple[str, str]:
    context = {
        "agent_name": _stringify(user.name),
        "agent_email": _stringify(user.email),
        "assignment_id": assignment.id,
        "module_title": _stringify(assignment.module_title),
        "peak_learning_time": _stringify(peak_learning_time),
        "task_type": _stringify(assignment.task_type).replace("_", " ").title(),
        "due_at": _stringify(assignment.due_at),
        "tracking_token": "",
    }

    title = _render_template_string(template.title_template, context).strip()
    body = _render_template_string(template.body_template, context).strip()
    return title, body
