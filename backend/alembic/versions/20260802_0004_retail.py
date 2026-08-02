"""零售库存迁移。

Revision ID: 20260802_0004
Revises: 20260802_0003
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0004"
down_revision: Union[str, None] = "20260802_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_product_categories_merchant_id", "product_categories", ["merchant_id"])

    op.create_table(
        "retail_skus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("product_categories.id")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("barcode", sa.String(64)),
        sa.Column("stock_qty", sa.Integer(), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_retail_skus_merchant_id", "retail_skus", ["merchant_id"])
    op.create_index("ix_retail_skus_category_id", "retail_skus", ["category_id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("retail_skus.id"), nullable=False),
        sa.Column("movement_type", sa.String(32), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id")),
        sa.Column("note", sa.String(255)),
        sa.Column("actor_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_stock_movements_merchant_id", "stock_movements", ["merchant_id"])
    op.create_index("ix_stock_movements_sku_id", "stock_movements", ["sku_id"])
    op.create_index("ix_stock_movements_order_id", "stock_movements", ["order_id"])

    op.create_table(
        "retail_order_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("fulfilled", sa.Boolean(), nullable=False),
        sa.Column("fulfill_error", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("order_id", name="uq_retail_order_link_order"),
    )
    op.create_index("ix_retail_order_links_order_id", "retail_order_links", ["order_id"])

    op.create_table(
        "retail_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_link_id", sa.Integer(), sa.ForeignKey("retail_order_links.id"), nullable=False),
        sa.Column("sku_id", sa.Integer(), sa.ForeignKey("retail_skus.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_retail_order_items_order_link_id", "retail_order_items", ["order_link_id"])
    op.create_index("ix_retail_order_items_sku_id", "retail_order_items", ["sku_id"])


def downgrade() -> None:
    op.drop_table("retail_order_items")
    op.drop_table("retail_order_links")
    op.drop_table("stock_movements")
    op.drop_table("retail_skus")
    op.drop_table("product_categories")
