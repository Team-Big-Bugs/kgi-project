"""align core notification schema names with project spec"""

from alembic import op
import sqlalchemy as sa


revision = "20260421_0002"
down_revision = "20260416_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notification_templates", recreate="always") as batch_op:
        batch_op.alter_column("id", new_column_name="template_id", existing_type=sa.Integer())
        batch_op.alter_column("body_template", new_column_name="message_body_string", existing_type=sa.Text())

    with op.batch_alter_table("agent_preferences", recreate="always") as batch_op:
        batch_op.alter_column("user_id", new_column_name="agent_id", existing_type=sa.Integer())

    op.drop_index(op.f("ix_dispatch_logs_user_id"), table_name="dispatch_logs")
    op.drop_index(op.f("ix_dispatch_logs_tracking_token"), table_name="dispatch_logs")
    op.drop_index(op.f("ix_dispatch_logs_scheduled_dispatch_time"), table_name="dispatch_logs")

    with op.batch_alter_table("dispatch_logs", recreate="always") as batch_op:
        batch_op.alter_column("id", new_column_name="dispatch_id", existing_type=sa.Integer())
        batch_op.alter_column("user_id", new_column_name="agent_id", existing_type=sa.Integer())
        batch_op.alter_column("opened_at", new_column_name="opened_timestamp", existing_type=sa.DateTime(timezone=True))

    op.create_index(op.f("ix_dispatch_logs_agent_id"), "dispatch_logs", ["agent_id"], unique=False)
    op.create_index(op.f("ix_dispatch_logs_tracking_token"), "dispatch_logs", ["tracking_token"], unique=False)
    op.create_index(op.f("ix_dispatch_logs_scheduled_dispatch_time"), "dispatch_logs", ["scheduled_dispatch_time"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dispatch_logs_agent_id"), table_name="dispatch_logs")
    op.drop_index(op.f("ix_dispatch_logs_tracking_token"), table_name="dispatch_logs")
    op.drop_index(op.f("ix_dispatch_logs_scheduled_dispatch_time"), table_name="dispatch_logs")

    with op.batch_alter_table("dispatch_logs", recreate="always") as batch_op:
        batch_op.alter_column("dispatch_id", new_column_name="id", existing_type=sa.Integer())
        batch_op.alter_column("agent_id", new_column_name="user_id", existing_type=sa.Integer())
        batch_op.alter_column("opened_timestamp", new_column_name="opened_at", existing_type=sa.DateTime(timezone=True))

    op.create_index(op.f("ix_dispatch_logs_user_id"), "dispatch_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_dispatch_logs_tracking_token"), "dispatch_logs", ["tracking_token"], unique=False)
    op.create_index(op.f("ix_dispatch_logs_scheduled_dispatch_time"), "dispatch_logs", ["scheduled_dispatch_time"], unique=False)

    with op.batch_alter_table("agent_preferences", recreate="always") as batch_op:
        batch_op.alter_column("agent_id", new_column_name="user_id", existing_type=sa.Integer())

    with op.batch_alter_table("notification_templates", recreate="always") as batch_op:
        batch_op.alter_column("template_id", new_column_name="id", existing_type=sa.Integer())
        batch_op.alter_column("message_body_string", new_column_name="body_template", existing_type=sa.Text())
