"""error_events 与 audit_logs.request_id

Revision ID: 20260902_0047
Revises: 20260828_0046
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0047"
down_revision: Union[str, None] = "20260828_0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("request_id", sa.String(64), nullable=True))
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])

    op.create_table(
        "error_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=True, index=True),
        sa.Column("audit_log_id", sa.Integer(), sa.ForeignKey("audit_logs.id"), nullable=True),
        sa.Column("level", sa.String(16), nullable=False, server_default="error"),
        sa.Column("source", sa.String(16), nullable=False, server_default="api"),
        sa.Column("error_code", sa.String(64), nullable=False, index=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("exception_type", sa.String(128), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("http_method", sa.String(16), nullable=True),
        sa.Column("request_path", sa.String(512), nullable=True),
        sa.Column("client_channel", sa.String(32), nullable=True),
        sa.Column("subsystem_code", sa.String(32), nullable=True),
        sa.Column("module", sa.String(64), nullable=True, index=True),
        sa.Column("actor_type", sa.String(32), nullable=True),
        sa.Column("actor_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
        sa.Column("actor_member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("actor_name", sa.String(128), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=True, index=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=True, index=True),
        sa.Column("client_ip", sa.String(64), nullable=True),
        sa.Column("extra_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("error_events")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_column("audit_logs", "request_id")
