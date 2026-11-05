"""Create tasks and durable idempotency records.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("char_length(btrim(title)) BETWEEN 1 AND 200", name="ck_task_title"),
        sa.CheckConstraint("char_length(description) <= 10000", name="ck_task_description"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')", name="ck_task_status"
        ),
        sa.CheckConstraint("priority BETWEEN 1 AND 5", name="ck_task_priority"),
        sa.CheckConstraint("version >= 1", name="ck_task_version"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_task_timestamps"),
    )
    op.create_index("ix_tasks_created_id", "tasks", ["created_at", "id"])
    op.create_index("ix_tasks_status_created_id", "tasks", ["status", "created_at", "id"])
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("key"),
        sa.CheckConstraint("char_length(key) BETWEEN 1 AND 128", name="ck_idempotency_key"),
        sa.CheckConstraint("char_length(fingerprint) = 64", name="ck_idempotency_fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_index("ix_tasks_status_created_id", table_name="tasks")
    op.drop_index("ix_tasks_created_id", table_name="tasks")
    op.drop_table("tasks")
