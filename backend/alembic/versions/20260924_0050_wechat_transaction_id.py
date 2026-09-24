"""支付意图记录微信支付订单号，便于对账

Revision ID: 20260924_0050
Revises: 20260924_0049
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0050"
down_revision: Union[str, None] = "20260924_0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payment_intents", sa.Column("wechat_transaction_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_intents", "wechat_transaction_id")
