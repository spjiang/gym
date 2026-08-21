"""20260820_0037 教练主关联会员；提成记录增加类别与教练追溯。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260820_0037"
down_revision = "20260820_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 员工账号改为可选：教练主身份挂会员
    op.alter_column("coaches", "staff_user_id", existing_type=sa.Integer(), nullable=True)

    op.add_column(
        "commission_records",
        sa.Column("category", sa.String(32), nullable=False, server_default="sale"),
    )
    op.add_column("commission_records", sa.Column("coach_id", sa.Integer(), nullable=True))
    op.create_index("ix_commission_records_category", "commission_records", ["category"])
    op.create_index("ix_commission_records_coach_id", "commission_records", ["coach_id"])
    op.create_foreign_key(
        "fk_commission_records_coach_id",
        "commission_records",
        "coaches",
        ["coach_id"],
        ["id"],
    )

    # 历史数据回填类别
    op.execute(
        """
        UPDATE commission_records
        SET category = CASE
            WHEN scope IN ('group_session', 'pt_session') THEN 'session'
            WHEN scope = 'referral' THEN 'referral'
            ELSE 'sale'
        END
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_commission_records_coach_id", "commission_records", type_="foreignkey")
    op.drop_index("ix_commission_records_coach_id", table_name="commission_records")
    op.drop_index("ix_commission_records_category", table_name="commission_records")
    op.drop_column("commission_records", "coach_id")
    op.drop_column("commission_records", "category")
    op.alter_column("coaches", "staff_user_id", existing_type=sa.Integer(), nullable=False)
