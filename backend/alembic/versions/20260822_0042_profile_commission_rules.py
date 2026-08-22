"""20260822_0042 销售/教练档案关联提成规则。"""

from alembic import op
import sqlalchemy as sa

revision = "20260822_0042"
down_revision = "20260822_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_reps",
        sa.Column("commission_rule_id", sa.Integer(), sa.ForeignKey("commission_rules.id"), nullable=True),
    )
    op.create_index("ix_sales_reps_commission_rule_id", "sales_reps", ["commission_rule_id"])

    op.add_column(
        "coaches",
        sa.Column("group_commission_rule_id", sa.Integer(), sa.ForeignKey("commission_rules.id"), nullable=True),
    )
    op.add_column(
        "coaches",
        sa.Column("pt_commission_rule_id", sa.Integer(), sa.ForeignKey("commission_rules.id"), nullable=True),
    )
    op.create_index("ix_coaches_group_commission_rule_id", "coaches", ["group_commission_rule_id"])
    op.create_index("ix_coaches_pt_commission_rule_id", "coaches", ["pt_commission_rule_id"])


def downgrade() -> None:
    op.drop_index("ix_coaches_pt_commission_rule_id", table_name="coaches")
    op.drop_index("ix_coaches_group_commission_rule_id", table_name="coaches")
    op.drop_column("coaches", "pt_commission_rule_id")
    op.drop_column("coaches", "group_commission_rule_id")
    op.drop_index("ix_sales_reps_commission_rule_id", table_name="sales_reps")
    op.drop_column("sales_reps", "commission_rule_id")
