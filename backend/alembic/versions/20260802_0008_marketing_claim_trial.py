"""营销增强：领券字段与体验卡标记。

Revision ID: 20260802_0008
Revises: 20260802_0007
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0008"
down_revision: Union[str, None] = "20260802_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "coupon_templates",
        sa.Column("claimable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "coupon_templates",
        sa.Column("per_member_limit", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "membership_products",
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("membership_products", "is_trial")
    op.drop_column("coupon_templates", "per_member_limit")
    op.drop_column("coupon_templates", "claimable")
