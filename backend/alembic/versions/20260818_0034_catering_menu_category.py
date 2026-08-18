"""20260818_0034 餐饮菜单分类。"""

from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision = "20260818_0034"
down_revision = "20260818_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catering_menu_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("merchant_id", "name", name="uq_catering_menu_category_merchant_name"),
    )
    op.create_index("ix_catering_menu_categories_merchant_id", "catering_menu_categories", ["merchant_id"])
    op.add_column(
        "catering_menu_items",
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("catering_menu_categories.id"), nullable=True),
    )
    op.create_index("ix_catering_menu_items_category_id", "catering_menu_items", ["category_id"])

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, merchant_id, category FROM catering_menu_items")).fetchall()
    cat_ids: dict[tuple[int, str], int] = {}
    sort_by_merchant: dict[int, int] = defaultdict(int)
    for item_id, merchant_id, category in rows:
        name = (category or "").strip() or "饮品"
        key = (int(merchant_id), name)
        if key not in cat_ids:
            sort_by_merchant[int(merchant_id)] += 10
            inserted = conn.execute(
                sa.text(
                    "INSERT INTO catering_menu_categories (merchant_id, name, sort_order, is_active) "
                    "VALUES (:mid, :name, :sort, true) RETURNING id"
                ),
                {"mid": merchant_id, "name": name, "sort": sort_by_merchant[int(merchant_id)]},
            )
            cat_ids[key] = int(inserted.scalar_one())
        conn.execute(
            sa.text("UPDATE catering_menu_items SET category = :name, category_id = :cid WHERE id = :id"),
            {"name": name, "cid": cat_ids[key], "id": item_id},
        )


def downgrade() -> None:
    op.drop_index("ix_catering_menu_items_category_id", table_name="catering_menu_items")
    op.drop_column("catering_menu_items", "category_id")
    op.drop_index("ix_catering_menu_categories_merchant_id", table_name="catering_menu_categories")
    op.drop_table("catering_menu_categories")
