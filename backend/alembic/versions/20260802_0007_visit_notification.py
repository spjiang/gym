"""临访与通知迁移。

Revision ID: 20260802_0007
Revises: 20260802_0006
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0007"
down_revision: Union[str, None] = "20260802_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visit_passes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("access_point_id", sa.Integer(), sa.ForeignKey("access_points.id"), nullable=False),
        sa.Column("grant_id", sa.Integer(), sa.ForeignKey("access_grants.id"), nullable=False),
        sa.Column("hours", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_visit_passes_merchant_id", "visit_passes", ["merchant_id"])
    op.create_index("ix_visit_passes_member_id", "visit_passes", ["member_id"])
    op.create_index("ix_visit_passes_grant_id", "visit_passes", ["grant_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("audience", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notifications_site_id", "notifications", ["site_id"])
    op.create_index("ix_notifications_merchant_id", "notifications", ["merchant_id"])
    op.create_index("ix_notifications_member_id", "notifications", ["member_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("visit_passes")
