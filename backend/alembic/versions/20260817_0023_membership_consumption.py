"""20260817_0023 会籍销次流水与会员推荐关系。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0023"
down_revision = "20260817_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "membership_consumptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("memberships.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("sessions", sa.Integer()),
        sa.Column("amount", sa.Numeric(12, 2)),
        sa.Column("remaining_sessions_after", sa.Integer()),
        sa.Column("balance_after", sa.Numeric(12, 2)),
        sa.Column("source", sa.String(32), nullable=False, server_default="front_desk"),
        sa.Column("note", sa.String(255)),
        sa.Column("actor_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_membership_consumptions_merchant_id", "membership_consumptions", ["merchant_id"]
    )
    op.create_index(
        "ix_membership_consumptions_membership_id", "membership_consumptions", ["membership_id"]
    )
    op.create_index("ix_membership_consumptions_member_id", "membership_consumptions", ["member_id"])
    op.create_index(
        "ix_membership_consumptions_actor_staff_id", "membership_consumptions", ["actor_staff_id"]
    )
    op.create_index(
        "ix_membership_consumptions_created_at", "membership_consumptions", ["created_at"]
    )

    op.add_column("members", sa.Column("referrer_member_id", sa.Integer(), sa.ForeignKey("members.id")))
    op.add_column("members", sa.Column("referrer_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")))
    op.add_column("members", sa.Column("referrer_note", sa.String(128)))
    op.add_column("members", sa.Column("referral_code", sa.String(32)))
    op.create_index("ix_members_referrer_member_id", "members", ["referrer_member_id"])
    op.create_index("ix_members_referrer_staff_id", "members", ["referrer_staff_id"])
    op.create_index("ix_members_referral_code", "members", ["referral_code"])

    op.add_column("orders", sa.Column("seller_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")))
    op.create_index("ix_orders_seller_staff_id", "orders", ["seller_staff_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_seller_staff_id", table_name="orders")
    op.drop_column("orders", "seller_staff_id")

    op.drop_index("ix_members_referral_code", table_name="members")
    op.drop_index("ix_members_referrer_staff_id", table_name="members")
    op.drop_index("ix_members_referrer_member_id", table_name="members")
    op.drop_column("members", "referral_code")
    op.drop_column("members", "referrer_note")
    op.drop_column("members", "referrer_staff_id")
    op.drop_column("members", "referrer_member_id")

    op.drop_index("ix_membership_consumptions_created_at", table_name="membership_consumptions")
    op.drop_index("ix_membership_consumptions_actor_staff_id", table_name="membership_consumptions")
    op.drop_index("ix_membership_consumptions_member_id", table_name="membership_consumptions")
    op.drop_index("ix_membership_consumptions_membership_id", table_name="membership_consumptions")
    op.drop_index("ix_membership_consumptions_merchant_id", table_name="membership_consumptions")
    op.drop_table("membership_consumptions")
