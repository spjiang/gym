"""微信平台公钥，用于回调验签

Revision ID: 20260902_0048
Revises: 20260902_0047
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0048"
down_revision: Union[str, None] = "20260902_0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("site_payment_settings", sa.Column("platform_serial_no", sa.String(128), nullable=True))
    op.add_column("site_payment_settings", sa.Column("platform_public_key_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("site_payment_settings", "platform_public_key_enc")
    op.drop_column("site_payment_settings", "platform_serial_no")
