"""会籍相关迁移。

Revision ID: 20260802_0002
Revises: 20260802_0001
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0002"
down_revision: Union[str, None] = "20260802_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "membership_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("product_type", sa.String(32), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("duration_days", sa.Integer()),
        sa.Column("session_count", sa.Integer()),
        sa.Column("stored_value", sa.Numeric(12, 2)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_membership_products_merchant_id", "membership_products", ["merchant_id"])

    op.create_table(
        "membership_product_access_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("membership_products.id"), nullable=False),
        sa.Column("access_point_id", sa.Integer(), sa.ForeignKey("access_points.id"), nullable=False),
        sa.UniqueConstraint("product_id", "access_point_id", name="uq_product_access_point"),
    )
    op.create_index("ix_mpap_product_id", "membership_product_access_points", ["product_id"])
    op.create_index("ix_mpap_access_point_id", "membership_product_access_points", ["access_point_id"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("membership_products.id"), nullable=False),
        sa.Column("product_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("remaining_sessions", sa.Integer()),
        sa.Column("balance", sa.Numeric(12, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_memberships_merchant_id", "memberships", ["merchant_id"])
    op.create_index("ix_memberships_member_id", "memberships", ["member_id"])
    op.create_index("ix_memberships_product_id", "memberships", ["product_id"])

    op.create_table(
        "membership_order_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("membership_products.id"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_membership_id", sa.Integer(), sa.ForeignKey("memberships.id")),
        sa.Column("fulfilled_membership_id", sa.Integer(), sa.ForeignKey("memberships.id")),
        sa.Column("fulfill_error", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("order_id", name="uq_membership_order_link_order"),
    )
    op.create_index("ix_membership_order_links_order_id", "membership_order_links", ["order_id"])


def downgrade() -> None:
    op.drop_table("membership_order_links")
    op.drop_table("memberships")
    op.drop_table("membership_product_access_points")
    op.drop_table("membership_products")
