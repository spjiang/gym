"""退款意图保存微信退款回传原文

Revision ID: 20260926_0053
Revises: 20260926_0052
Create Date: 2026-09-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260926_0053"
down_revision: Union[str, None] = "20260926_0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("refund_intents", sa.Column("wechat_payload", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("refund_intents", "wechat_payload")
