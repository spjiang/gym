"""init platform foundation

Revision ID: 20260802_0001
Revises:
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("address", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "merchant_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.UniqueConstraint("code", name="uq_merchant_types_code"),
    )
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_type_id", sa.Integer(), sa.ForeignKey("merchant_types.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_merchants_site_id", "merchants", ["site_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("is_site_scope", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_table(
        "staff_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("username", name="uq_staff_users_username"),
    )
    op.create_index("ix_staff_users_site_id", "staff_users", ["site_id"])
    op.create_index("ix_staff_users_merchant_id", "staff_users", ["merchant_id"])

    op.create_table(
        "staff_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.UniqueConstraint("staff_id", "role_id", name="uq_staff_role"),
    )

    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("face_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("site_id", "phone", name="uq_members_site_phone"),
    )
    op.create_index("ix_members_site_id", "members", ["site_id"])

    op.create_table(
        "merchant_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("merchant_id", "member_id", name="uq_merchant_member"),
    )

    op.create_table(
        "access_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_public_area", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "access_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("access_point_id", sa.Integer(), sa.ForeignKey("access_points.id"), nullable=False),
        sa.Column("device_code", sa.String(64), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("is_online", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("device_code", name="uq_access_devices_code"),
    )
    op.create_table(
        "access_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("access_point_id", sa.Integer(), sa.ForeignKey("access_points.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "access_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("access_devices.id"), nullable=False),
        sa.Column("access_point_id", sa.Integer(), sa.ForeignKey("access_points.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(128)),
        sa.Column("detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("order_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id")),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("actor_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    for table in [
        "audit_logs",
        "payments",
        "orders",
        "access_events",
        "access_grants",
        "access_devices",
        "access_points",
        "merchant_members",
        "members",
        "staff_roles",
        "staff_users",
        "roles",
        "merchants",
        "merchant_types",
        "sites",
    ]:
        op.drop_table(table)
