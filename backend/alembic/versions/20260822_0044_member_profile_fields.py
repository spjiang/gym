"""会员档案扩展字段

Revision ID: 20260822_0044
Revises: 20260822_0043
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0044"
down_revision: Union[str, None] = "20260822_0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("members", sa.Column("gender", sa.String(16), nullable=True))
    op.add_column("members", sa.Column("birthday", sa.Date(), nullable=True))
    op.add_column("members", sa.Column("email", sa.String(128), nullable=True))
    op.add_column("members", sa.Column("remark", sa.Text(), nullable=True))
    op.add_column("members", sa.Column("emergency_contact", sa.String(64), nullable=True))
    op.add_column("members", sa.Column("emergency_phone", sa.String(32), nullable=True))


def downgrade() -> None:
    for col in ["emergency_phone", "emergency_contact", "remark", "email", "birthday", "gender"]:
        op.drop_column("members", col)
