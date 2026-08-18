"""20260817_0027 推广配置：返点满多少天才能提现。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0027"
down_revision = "20260817_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "site_promotion_settings",
        sa.Column("withdraw_hold_days", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("site_promotion_settings", "withdraw_hold_days")
