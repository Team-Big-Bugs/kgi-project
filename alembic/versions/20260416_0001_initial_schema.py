"""initial schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260416_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Enum("agent", "admin", name="user_role"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("line_user_id", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("line_user_id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "agent_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("preferred_channel", sa.Enum("PUSH", "EMAIL", "LINE", name="channel_type"), nullable=False),
        sa.Column("dnd_start_time", sa.Time(), nullable=True),
        sa.Column("dnd_end_time", sa.Time(), nullable=True),
        sa.Column("is_opted_out", sa.Boolean(), nullable=False),
        sa.Column("peak_learning_time", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "learning_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("module_title", sa.String(length=255), nullable=False),
        sa.Column(
            "task_type",
            sa.Enum("mandatory_module", "memory_recall", name="task_type"),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_assignments_due_at"), "learning_assignments", ["due_at"], unique=False)
    op.create_index(op.f("ix_learning_assignments_user_id"), "learning_assignments", ["user_id"], unique=False)

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "trigger_type",
            sa.Enum("bio_rhythm_peak", "streak_warning", "spaced_repetition_due", name="trigger_type"),
            nullable=False,
        ),
        sa.Column(
            "channel_type",
            sa.Enum("PUSH", "EMAIL", "LINE", name="template_channel_type"),
            nullable=False,
        ),
        sa.Column("title_template", sa.String(length=255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "line_link_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("link_code", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "linked", "expired", "cancelled", name="line_link_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link_code"),
    )
    op.create_index(op.f("ix_line_link_requests_link_code"), "line_link_requests", ["link_code"], unique=True)
    op.create_index(op.f("ix_line_link_requests_user_id"), "line_link_requests", ["user_id"], unique=False)

    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(length=1000), nullable=False),
        sa.Column("p256dh_key", sa.String(length=255), nullable=False),
        sa.Column("auth_key", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint", name="uq_web_push_subscriptions_endpoint"),
    )
    op.create_index(op.f("ix_web_push_subscriptions_user_id"), "web_push_subscriptions", ["user_id"], unique=False)

    op.create_table(
        "dispatch_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("learning_assignment_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column(
            "channel_type",
            sa.Enum("PUSH", "EMAIL", "LINE", name="dispatch_channel_type"),
            nullable=False,
        ),
        sa.Column("scheduled_dispatch_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("queued", "sent", "failed", name="dispatch_status"), nullable=False),
        sa.Column("tracking_token", sa.String(length=255), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["learning_assignment_id"], ["learning_assignments.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["notification_templates.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_dispatch_logs_dedupe_key"),
        sa.UniqueConstraint("tracking_token"),
    )
    op.create_index(op.f("ix_dispatch_logs_scheduled_dispatch_time"), "dispatch_logs", ["scheduled_dispatch_time"], unique=False)
    op.create_index(op.f("ix_dispatch_logs_tracking_token"), "dispatch_logs", ["tracking_token"], unique=False)
    op.create_index(op.f("ix_dispatch_logs_user_id"), "dispatch_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dispatch_logs_user_id"), table_name="dispatch_logs")
    op.drop_index(op.f("ix_dispatch_logs_tracking_token"), table_name="dispatch_logs")
    op.drop_index(op.f("ix_dispatch_logs_scheduled_dispatch_time"), table_name="dispatch_logs")
    op.drop_table("dispatch_logs")
    op.drop_index(op.f("ix_web_push_subscriptions_user_id"), table_name="web_push_subscriptions")
    op.drop_table("web_push_subscriptions")
    op.drop_index(op.f("ix_line_link_requests_user_id"), table_name="line_link_requests")
    op.drop_index(op.f("ix_line_link_requests_link_code"), table_name="line_link_requests")
    op.drop_table("line_link_requests")
    op.drop_table("notification_templates")
    op.drop_index(op.f("ix_learning_assignments_user_id"), table_name="learning_assignments")
    op.drop_index(op.f("ix_learning_assignments_due_at"), table_name="learning_assignments")
    op.drop_table("learning_assignments")
    op.drop_table("agent_preferences")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    sa.Enum(name="dispatch_status").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="dispatch_channel_type").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="line_link_status").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="template_channel_type").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="trigger_type").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="task_type").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="channel_type").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=False)
