"""20260817_0025 业务分成体系与推广位。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0025"
down_revision = "20260817_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commission_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("beneficiary", sa.String(32), nullable=False),
        sa.Column("basis", sa.String(32), nullable=False),
        sa.Column("rate", sa.Numeric(7, 4)),
        sa.Column("unit_amount", sa.Numeric(12, 2)),
        sa.Column("min_base_amount", sa.Numeric(12, 2)),
        sa.Column("max_amount", sa.Numeric(12, 2)),
        sa.Column("first_order_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_commission_rules_merchant_id", "commission_rules", ["merchant_id"])
    op.create_index("ix_commission_rules_scope", "commission_rules", ["scope"])

    op.create_table(
        "commission_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("commission_rules.id")),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id")),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("beneficiary_type", sa.String(16), nullable=False),
        sa.Column("beneficiary_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_name", sa.String(128), nullable=False),
        sa.Column("base_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Integer()),
        sa.Column("rate", sa.Numeric(7, 4)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("note", sa.String(255)),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "scope",
            "source_type",
            "source_id",
            "beneficiary_type",
            "beneficiary_id",
            name="uq_commission_record_source_beneficiary",
        ),
    )
    op.create_index("ix_commission_records_merchant_id", "commission_records", ["merchant_id"])
    op.create_index("ix_commission_records_rule_id", "commission_records", ["rule_id"])
    op.create_index("ix_commission_records_scope", "commission_records", ["scope"])
    op.create_index("ix_commission_records_source_id", "commission_records", ["source_id"])
    op.create_index("ix_commission_records_order_id", "commission_records", ["order_id"])
    op.create_index("ix_commission_records_member_id", "commission_records", ["member_id"])
    op.create_index("ix_commission_records_beneficiary_id", "commission_records", ["beneficiary_id"])
    op.create_index("ix_commission_records_created_at", "commission_records", ["created_at"])

    op.create_table(
        "promoter_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id")),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("subject_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("channel", sa.String(32), nullable=False, server_default="other"),
        sa.Column("landing_path", sa.String(128)),
        sa.Column("commission_rule_id", sa.Integer(), sa.ForeignKey("commission_rules.id")),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_promoter_code"),
    )
    op.create_index("ix_promoter_codes_site_id", "promoter_codes", ["site_id"])
    op.create_index("ix_promoter_codes_merchant_id", "promoter_codes", ["merchant_id"])
    op.create_index("ix_promoter_codes_subject_member_id", "promoter_codes", ["subject_member_id"])
    op.create_index("ix_promoter_codes_subject_staff_id", "promoter_codes", ["subject_staff_id"])
    op.create_index("ix_promoter_codes_commission_rule_id", "promoter_codes", ["commission_rule_id"])


def downgrade() -> None:
    op.drop_index("ix_promoter_codes_commission_rule_id", table_name="promoter_codes")
    op.drop_index("ix_promoter_codes_subject_staff_id", table_name="promoter_codes")
    op.drop_index("ix_promoter_codes_subject_member_id", table_name="promoter_codes")
    op.drop_index("ix_promoter_codes_merchant_id", table_name="promoter_codes")
    op.drop_index("ix_promoter_codes_site_id", table_name="promoter_codes")
    op.drop_table("promoter_codes")

    op.drop_index("ix_commission_records_created_at", table_name="commission_records")
    op.drop_index("ix_commission_records_beneficiary_id", table_name="commission_records")
    op.drop_index("ix_commission_records_member_id", table_name="commission_records")
    op.drop_index("ix_commission_records_order_id", table_name="commission_records")
    op.drop_index("ix_commission_records_source_id", table_name="commission_records")
    op.drop_index("ix_commission_records_scope", table_name="commission_records")
    op.drop_index("ix_commission_records_rule_id", table_name="commission_records")
    op.drop_index("ix_commission_records_merchant_id", table_name="commission_records")
    op.drop_table("commission_records")

    op.drop_index("ix_commission_rules_scope", table_name="commission_rules")
    op.drop_index("ix_commission_rules_merchant_id", table_name="commission_rules")
    op.drop_table("commission_rules")
