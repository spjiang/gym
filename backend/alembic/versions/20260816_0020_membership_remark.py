"""20260816_0020 会籍备注。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0020"
down_revision = "20260816_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memberships", sa.Column("remark", sa.Text()))


def downgrade() -> None:
    op.drop_column("memberships", "remark")
