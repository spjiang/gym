"""订单取餐号与顾客备注。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260804_0012"
down_revision = "20260804_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("pickup_code", sa.String(16), nullable=True))
    op.add_column("orders", sa.Column("customer_note", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "customer_note")
    op.drop_column("orders", "pickup_code")
