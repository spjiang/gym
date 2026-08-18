"""20260817_0028 会员展示头像。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0028"
down_revision = "20260817_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("members", sa.Column("avatar_url", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "avatar_url")
