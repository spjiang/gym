"""一期收口：活动价字段与 OTP 挑战表。

Revision ID: 20260802_0009
Revises: 20260802_0008
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0009"
down_revision: Union[str, None] = "20260802_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("membership_products", "retail_skus", "pt_package_products"):
        op.add_column(table, sa.Column("promo_price", sa.Numeric(12, 2)))
        op.add_column(table, sa.Column("promo_starts_at", sa.DateTime(timezone=True)))
        op.add_column(table, sa.Column("promo_ends_at", sa.DateTime(timezone=True)))

    op.create_table(
        "member_otp_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_otp_challenges_member_id", "member_otp_challenges", ["member_id"])
    op.create_index("ix_member_otp_challenges_phone", "member_otp_challenges", ["phone"])


def downgrade() -> None:
    op.drop_table("member_otp_challenges")
    for table in ("pt_package_products", "retail_skus", "membership_products"):
        op.drop_column(table, "promo_ends_at")
        op.drop_column(table, "promo_starts_at")
        op.drop_column(table, "promo_price")
