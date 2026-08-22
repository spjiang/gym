"""20260822_0041 销售档案与移除员工推荐。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260822_0041"
down_revision = "20260822_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_reps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("staff_user_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("staff_user_id", name="uq_sales_reps_staff_user"),
        sa.UniqueConstraint("member_id", name="uq_sales_reps_member"),
    )
    op.create_index("ix_sales_reps_merchant_id", "sales_reps", ["merchant_id"])
    op.create_index("ix_sales_reps_staff_user_id", "sales_reps", ["staff_user_id"])
    op.create_index("ix_sales_reps_member_id", "sales_reps", ["member_id"])

    op.drop_index("ix_members_referrer_staff_id", table_name="members")
    op.drop_column("members", "referrer_staff_id")

    op.drop_index("ix_promoter_codes_subject_staff_id", table_name="promoter_codes")
    op.drop_column("promoter_codes", "subject_staff_id")


def downgrade() -> None:
    op.add_column("promoter_codes", sa.Column("subject_staff_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "promoter_codes_subject_staff_id_fkey",
        "promoter_codes",
        "staff_users",
        ["subject_staff_id"],
        ["id"],
    )
    op.create_index("ix_promoter_codes_subject_staff_id", "promoter_codes", ["subject_staff_id"])

    op.add_column("members", sa.Column("referrer_staff_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "members_referrer_staff_id_fkey", "members", "staff_users", ["referrer_staff_id"], ["id"]
    )
    op.create_index("ix_members_referrer_staff_id", "members", ["referrer_staff_id"])

    op.drop_index("ix_sales_reps_member_id", table_name="sales_reps")
    op.drop_index("ix_sales_reps_staff_user_id", table_name="sales_reps")
    op.drop_index("ix_sales_reps_merchant_id", table_name="sales_reps")
    op.drop_table("sales_reps")
