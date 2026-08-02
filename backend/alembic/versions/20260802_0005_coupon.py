"""优惠券迁移。

Revision ID: 20260802_0005
Revises: 20260802_0004
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0005"
down_revision: Union[str, None] = "20260802_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coupon_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("discount_type", sa.String(32), nullable=False),
        sa.Column("threshold_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("fixed_amount", sa.Numeric(12, 2)),
        sa.Column("percent_off", sa.Integer()),
        sa.Column("applicable_to", sa.String(32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_limit", sa.Integer()),
        sa.Column("issued_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_coupon_templates_merchant_id", "coupon_templates", ["merchant_id"])

    op.create_table(
        "member_coupons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("coupon_templates.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_order_id", sa.Integer(), sa.ForeignKey("orders.id")),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_coupons_merchant_id", "member_coupons", ["merchant_id"])
    op.create_index("ix_member_coupons_template_id", "member_coupons", ["template_id"])
    op.create_index("ix_member_coupons_member_id", "member_coupons", ["member_id"])

    op.create_table(
        "order_coupon_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("member_coupon_id", sa.Integer(), sa.ForeignKey("member_coupons.id"), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("order_id", name="uq_order_coupon_link_order"),
    )
    op.create_index("ix_order_coupon_links_order_id", "order_coupon_links", ["order_id"])
    op.create_index("ix_order_coupon_links_member_coupon_id", "order_coupon_links", ["member_coupon_id"])


def downgrade() -> None:
    op.drop_table("order_coupon_links")
    op.drop_table("member_coupons")
    op.drop_table("coupon_templates")
