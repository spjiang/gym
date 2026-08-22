"""20260822_0040 提成结算冷却与已打款退款欠额。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260822_0040"
down_revision = "20260822_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_commission_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("settle_hold_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("updated_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", name="uq_site_commission_settings_site"),
    )
    op.create_index("ix_site_commission_settings_site_id", "site_commission_settings", ["site_id"])

    op.create_table(
        "commission_debt_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("beneficiary_type", sa.String(16), nullable=False),
        sa.Column("beneficiary_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("debt_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "site_id",
            "beneficiary_type",
            "beneficiary_id",
            name="uq_commission_debt_account_beneficiary",
        ),
    )
    op.create_index("ix_commission_debt_accounts_site_id", "commission_debt_accounts", ["site_id"])
    op.create_index(
        "ix_commission_debt_accounts_beneficiary_id", "commission_debt_accounts", ["beneficiary_id"]
    )

    op.create_table(
        "commission_clawback_ledgers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("commission_debt_accounts.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column(
            "commission_record_id",
            sa.Integer(),
            sa.ForeignKey("commission_records.id"),
            nullable=True,
        ),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("actor_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "kind",
            "source_type",
            "source_id",
            "commission_record_id",
            name="uq_commission_clawback_source",
        ),
    )
    op.create_index("ix_commission_clawback_ledgers_site_id", "commission_clawback_ledgers", ["site_id"])
    op.create_index("ix_commission_clawback_ledgers_account_id", "commission_clawback_ledgers", ["account_id"])
    op.create_index("ix_commission_clawback_ledgers_kind", "commission_clawback_ledgers", ["kind"])
    op.create_index(
        "ix_commission_clawback_ledgers_commission_record_id",
        "commission_clawback_ledgers",
        ["commission_record_id"],
    )
    op.create_index("ix_commission_clawback_ledgers_order_id", "commission_clawback_ledgers", ["order_id"])
    op.create_index("ix_commission_clawback_ledgers_created_at", "commission_clawback_ledgers", ["created_at"])

    op.add_column(
        "payouts",
        sa.Column("offset_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("payouts", "offset_amount")
    op.drop_index("ix_commission_clawback_ledgers_created_at", table_name="commission_clawback_ledgers")
    op.drop_index("ix_commission_clawback_ledgers_order_id", table_name="commission_clawback_ledgers")
    op.drop_index(
        "ix_commission_clawback_ledgers_commission_record_id",
        table_name="commission_clawback_ledgers",
    )
    op.drop_index("ix_commission_clawback_ledgers_kind", table_name="commission_clawback_ledgers")
    op.drop_index("ix_commission_clawback_ledgers_account_id", table_name="commission_clawback_ledgers")
    op.drop_index("ix_commission_clawback_ledgers_site_id", table_name="commission_clawback_ledgers")
    op.drop_table("commission_clawback_ledgers")
    op.drop_index("ix_commission_debt_accounts_beneficiary_id", table_name="commission_debt_accounts")
    op.drop_index("ix_commission_debt_accounts_site_id", table_name="commission_debt_accounts")
    op.drop_table("commission_debt_accounts")
    op.drop_index("ix_site_commission_settings_site_id", table_name="site_commission_settings")
    op.drop_table("site_commission_settings")
