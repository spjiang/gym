"""20260818_0033 餐饮桌台：桌号与点餐码。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260818_0033"
down_revision = "20260818_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catering_tables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("merchant_id", "name", name="uq_catering_table_merchant_name"),
        sa.UniqueConstraint("code", name="uq_catering_table_code"),
    )
    op.create_index("ix_catering_tables_merchant_id", "catering_tables", ["merchant_id"])


def downgrade() -> None:
    op.drop_index("ix_catering_tables_merchant_id", table_name="catering_tables")
    op.drop_table("catering_tables")
