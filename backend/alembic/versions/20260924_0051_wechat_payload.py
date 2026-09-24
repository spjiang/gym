"""支付意图保存微信回调/查单原文

Revision ID: 20260924_0051
Revises: 20260924_0050
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260924_0051"
down_revision: Union[str, None] = "20260924_0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payment_intents", sa.Column("wechat_payload", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_intents", "wechat_payload")
