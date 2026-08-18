"""20260817_0031 餐饮后厨履约状态。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0031"
down_revision = "20260817_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("dining_status", sa.String(length=32), nullable=True))
    op.execute(
        sa.text(
            "UPDATE orders SET dining_status = 'preparing' "
            "WHERE order_type = 'dining' AND status = 'paid' AND dining_status IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("orders", "dining_status")
