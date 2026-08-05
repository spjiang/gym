"""20260805_0015 支付退款加固：累计退款额与退款意图。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260805_0015"
down_revision = "20260805_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("refunded_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "refund_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("out_refund_no", sa.String(64), nullable=False),
        sa.Column("out_trade_no", sa.String(64)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("suggested_amount", sa.Numeric(12, 2)),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("force", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reason", sa.String(255)),
        sa.Column("provider_ref", sa.String(128)),
        sa.Column("error_message", sa.String(512)),
        sa.Column("actor_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("succeeded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("out_refund_no", name="uq_refund_intents_out_refund_no"),
    )
    op.create_index("ix_refund_intents_site_id", "refund_intents", ["site_id"])
    op.create_index("ix_refund_intents_order_id", "refund_intents", ["order_id"])
    op.create_index("ix_refund_intents_status", "refund_intents", ["status"])


def downgrade() -> None:
    op.drop_table("refund_intents")
    op.drop_column("orders", "refunded_amount")
