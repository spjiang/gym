"""会员获客来源字段；OTP 挑战允许无会员。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260805_0013"
down_revision = "20260804_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("acquisition_source", sa.String(32), nullable=False, server_default="platform"),
    )
    op.add_column(
        "members",
        sa.Column("first_merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=True),
    )
    op.create_index("ix_members_first_merchant_id", "members", ["first_merchant_id"])

    # OTP 支持未注册手机号发码
    op.alter_column(
        "member_otp_challenges",
        "member_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 回填：有挂靠 → merchant + 最早关联商户
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE members AS m
                SET acquisition_source = 'merchant',
                    first_merchant_id = sub.mid
                FROM (
                    SELECT member_id, MIN(merchant_id) AS mid
                    FROM merchant_members
                    GROUP BY member_id
                ) AS sub
                WHERE m.id = sub.member_id
                """
            )
        )
    else:
        # SQLite 等：逐行回填
        rows = bind.execute(sa.text("SELECT member_id, MIN(merchant_id) FROM merchant_members GROUP BY member_id")).fetchall()
        for member_id, mid in rows:
            bind.execute(
                sa.text(
                    "UPDATE members SET acquisition_source = 'merchant', first_merchant_id = :mid WHERE id = :id"
                ),
                {"mid": mid, "id": member_id},
            )


def downgrade() -> None:
    op.alter_column(
        "member_otp_challenges",
        "member_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_index("ix_members_first_merchant_id", table_name="members")
    op.drop_column("members", "first_merchant_id")
    op.drop_column("members", "acquisition_source")
