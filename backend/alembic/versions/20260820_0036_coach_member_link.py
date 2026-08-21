"""20260820_0036 教练档案关联会员主档，统一走会员推广机制。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260820_0036"
down_revision = "20260819_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("coaches", sa.Column("member_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_coaches_member_id",
        "coaches",
        "members",
        ["member_id"],
        ["id"],
    )
    op.create_index("ix_coaches_member_id", "coaches", ["member_id"])


def downgrade() -> None:
    op.drop_index("ix_coaches_member_id", table_name="coaches")
    op.drop_constraint("fk_coaches_member_id", "coaches", type_="foreignkey")
    op.drop_column("coaches", "member_id")
