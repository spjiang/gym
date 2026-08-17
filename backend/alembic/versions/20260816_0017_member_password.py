"""20260816_0017 会员登录密码。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0017"
down_revision = "20260815_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("members", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "password_hash")
