"""平台订单号，GY 开头

Revision ID: 20260924_0049
Revises: 20260902_0048
Create Date: 2026-09-24
"""

from datetime import datetime
from typing import Sequence, Union
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0049"
down_revision: Union[str, None] = "20260902_0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def upgrade() -> None:
    op.add_column("orders", sa.Column("order_no", sa.String(length=32), nullable=True))
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, created_at FROM orders WHERE order_no IS NULL ORDER BY id")).fetchall()
    for row in rows:
        created = row.created_at
        if isinstance(created, datetime):
            if created.tzinfo is None:
                created = created.replace(tzinfo=ZoneInfo("UTC"))
            stamp = created.astimezone(_SHANGHAI).strftime("%Y%m%d%H%M%S")
        else:
            stamp = "20260101000000"
        order_no = f"GY{stamp}{int(row.id):06d}"
        conn.execute(
            sa.text("UPDATE orders SET order_no = :order_no WHERE id = :id"),
            {"order_no": order_no, "id": row.id},
        )
    op.create_unique_constraint("uq_orders_order_no", "orders", ["order_no"])
    op.alter_column("orders", "order_no", existing_type=sa.String(length=32), nullable=False)


def downgrade() -> None:
    op.drop_constraint("uq_orders_order_no", "orders", type_="unique")
    op.drop_column("orders", "order_no")
