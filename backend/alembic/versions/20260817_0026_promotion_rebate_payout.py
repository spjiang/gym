"""20260817_0026 统一推广方案：会员返点账户、下级折扣与提现单。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0026"
down_revision = "20260817_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 推广位：返点比例与下级折扣，会员推广位一人一码
    op.add_column("promoter_codes", sa.Column("rebate_rate", sa.Numeric(7, 4)))
    op.add_column("promoter_codes", sa.Column("downline_discount_rate", sa.Numeric(7, 4)))
    op.create_index(
        "uq_promoter_member_code",
        "promoter_codes",
        ["site_id", "subject_member_id"],
        unique=True,
        postgresql_where=sa.text("subject_type = 'member'"),
        sqlite_where=sa.text("subject_type = 'member'"),
    )

    # 订单：区分原价、推广折扣与实付
    op.add_column("orders", sa.Column("original_amount", sa.Numeric(12, 2)))
    op.add_column(
        "orders",
        sa.Column(
            "promotion_discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"
        ),
    )
    op.add_column("orders", sa.Column("promoter_code", sa.String(32)))
    op.create_index("ix_orders_promoter_code", "orders", ["promoter_code"])
    # 历史订单无折扣，原价即实付
    op.execute("UPDATE orders SET original_amount = amount WHERE original_amount IS NULL")

    # 教练个人私教佣金比例
    op.add_column("coaches", sa.Column("pt_commission_rate", sa.Numeric(7, 4)))

    op.create_table(
        "site_promotion_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column(
            "auto_create_member_code", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("default_rebate_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column(
            "default_downline_discount_rate", sa.Numeric(7, 4), nullable=False, server_default="0"
        ),
        sa.Column("min_withdraw_amount", sa.Numeric(12, 2), nullable=False, server_default="1.00"),
        sa.Column("remark", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("site_id", name="uq_site_promotion_settings_site"),
    )
    op.create_index("ix_site_promotion_settings_site_id", "site_promotion_settings", ["site_id"])

    op.create_table(
        "member_rebate_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("frozen_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("debt_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_earned", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_withdrawn", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("member_id", name="uq_member_rebate_account_member"),
    )
    op.create_index("ix_member_rebate_accounts_site_id", "member_rebate_accounts", ["site_id"])
    op.create_index("ix_member_rebate_accounts_member_id", "member_rebate_accounts", ["member_id"])

    op.create_table(
        "member_rebate_ledgers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column(
            "account_id", sa.Integer(), sa.ForeignKey("member_rebate_accounts.id"), nullable=False
        ),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("source_type", sa.String(32)),
        sa.Column("source_id", sa.Integer()),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id")),
        sa.Column("from_member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("base_amount", sa.Numeric(12, 2)),
        sa.Column("rate", sa.Numeric(7, 4)),
        sa.Column("note", sa.String(255)),
        sa.Column("actor_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "kind", "source_type", "source_id", name="uq_member_rebate_ledger_source"
        ),
    )
    op.create_index("ix_member_rebate_ledgers_site_id", "member_rebate_ledgers", ["site_id"])
    op.create_index("ix_member_rebate_ledgers_account_id", "member_rebate_ledgers", ["account_id"])
    op.create_index("ix_member_rebate_ledgers_member_id", "member_rebate_ledgers", ["member_id"])
    op.create_index(
        "ix_member_rebate_ledgers_merchant_id", "member_rebate_ledgers", ["merchant_id"]
    )
    op.create_index("ix_member_rebate_ledgers_order_id", "member_rebate_ledgers", ["order_id"])
    op.create_index(
        "ix_member_rebate_ledgers_from_member_id", "member_rebate_ledgers", ["from_member_id"]
    )
    op.create_index("ix_member_rebate_ledgers_created_at", "member_rebate_ledgers", ["created_at"])

    op.create_table(
        "payouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("beneficiary_type", sa.String(16), nullable=False),
        sa.Column("beneficiary_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_name", sa.String(128), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="requested"),
        sa.Column("method", sa.String(32)),
        sa.Column("external_ref", sa.String(64)),
        sa.Column("note", sa.String(255)),
        sa.Column("reject_reason", sa.String(255)),
        sa.Column("requested_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("requested_by_member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("reviewed_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("paid_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payouts_site_id", "payouts", ["site_id"])
    op.create_index("ix_payouts_merchant_id", "payouts", ["merchant_id"])
    op.create_index("ix_payouts_source", "payouts", ["source"])
    op.create_index("ix_payouts_status", "payouts", ["status"])
    op.create_index("ix_payouts_beneficiary_id", "payouts", ["beneficiary_id"])
    op.create_index("ix_payouts_created_at", "payouts", ["created_at"])

    op.create_table(
        "payout_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payout_id", sa.Integer(), sa.ForeignKey("payouts.id"), nullable=False),
        sa.Column(
            "commission_record_id",
            sa.Integer(),
            sa.ForeignKey("commission_records.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("commission_record_id", name="uq_payout_item_commission_record"),
    )
    op.create_index("ix_payout_items_payout_id", "payout_items", ["payout_id"])


def downgrade() -> None:
    op.drop_index("ix_payout_items_payout_id", table_name="payout_items")
    op.drop_table("payout_items")

    op.drop_index("ix_payouts_created_at", table_name="payouts")
    op.drop_index("ix_payouts_beneficiary_id", table_name="payouts")
    op.drop_index("ix_payouts_status", table_name="payouts")
    op.drop_index("ix_payouts_source", table_name="payouts")
    op.drop_index("ix_payouts_merchant_id", table_name="payouts")
    op.drop_index("ix_payouts_site_id", table_name="payouts")
    op.drop_table("payouts")

    op.drop_index("ix_member_rebate_ledgers_created_at", table_name="member_rebate_ledgers")
    op.drop_index("ix_member_rebate_ledgers_from_member_id", table_name="member_rebate_ledgers")
    op.drop_index("ix_member_rebate_ledgers_order_id", table_name="member_rebate_ledgers")
    op.drop_index("ix_member_rebate_ledgers_merchant_id", table_name="member_rebate_ledgers")
    op.drop_index("ix_member_rebate_ledgers_member_id", table_name="member_rebate_ledgers")
    op.drop_index("ix_member_rebate_ledgers_account_id", table_name="member_rebate_ledgers")
    op.drop_index("ix_member_rebate_ledgers_site_id", table_name="member_rebate_ledgers")
    op.drop_table("member_rebate_ledgers")

    op.drop_index("ix_member_rebate_accounts_member_id", table_name="member_rebate_accounts")
    op.drop_index("ix_member_rebate_accounts_site_id", table_name="member_rebate_accounts")
    op.drop_table("member_rebate_accounts")

    op.drop_index("ix_site_promotion_settings_site_id", table_name="site_promotion_settings")
    op.drop_table("site_promotion_settings")

    op.drop_column("coaches", "pt_commission_rate")

    op.drop_index("ix_orders_promoter_code", table_name="orders")
    op.drop_column("orders", "promoter_code")
    op.drop_column("orders", "promotion_discount_amount")
    op.drop_column("orders", "original_amount")

    op.drop_index("uq_promoter_member_code", table_name="promoter_codes")
    op.drop_column("promoter_codes", "downline_discount_rate")
    op.drop_column("promoter_codes", "rebate_rate")
