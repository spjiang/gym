"""audit_logs 字段扩展

Revision ID: 20260822_0043
Revises: 20260822_0042
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0043"
down_revision: Union[str, None] = "20260822_0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("actor_member_id", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_type", sa.String(32), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_name", sa.String(128), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_account", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("subsystem_code", sa.String(32), nullable=True))
    op.add_column("audit_logs", sa.Column("module", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("client_channel", sa.String(32), nullable=True))
    op.add_column("audit_logs", sa.Column("http_method", sa.String(16), nullable=True))
    op.add_column("audit_logs", sa.Column("request_path", sa.String(512), nullable=True))
    op.add_column("audit_logs", sa.Column("client_ip", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(512), nullable=True))
    op.add_column("audit_logs", sa.Column("status", sa.String(16), nullable=True))
    op.add_column("audit_logs", sa.Column("status_code", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("detail_json", sa.JSON(), nullable=True))

    op.create_foreign_key(
        "fk_audit_logs_actor_member_id",
        "audit_logs",
        "members",
        ["actor_member_id"],
        ["id"],
    )
    op.create_index("ix_audit_logs_actor_member_id", "audit_logs", ["actor_member_id"])
    op.create_index("ix_audit_logs_actor_type", "audit_logs", ["actor_type"])
    op.create_index("ix_audit_logs_subsystem_code", "audit_logs", ["subsystem_code"])
    op.create_index("ix_audit_logs_module", "audit_logs", ["module"])
    op.create_index("ix_audit_logs_client_channel", "audit_logs", ["client_channel"])
    op.create_index("ix_audit_logs_status", "audit_logs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_status", table_name="audit_logs")
    op.drop_index("ix_audit_logs_client_channel", table_name="audit_logs")
    op.drop_index("ix_audit_logs_module", table_name="audit_logs")
    op.drop_index("ix_audit_logs_subsystem_code", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_member_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_actor_member_id", "audit_logs", type_="foreignkey")
    for col in [
        "detail_json",
        "duration_ms",
        "status_code",
        "status",
        "user_agent",
        "client_ip",
        "request_path",
        "http_method",
        "client_channel",
        "module",
        "subsystem_code",
        "actor_account",
        "actor_name",
        "actor_type",
        "actor_member_id",
    ]:
        op.drop_column("audit_logs", col)
