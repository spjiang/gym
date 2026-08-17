"""20260816_0021 零售商品备注与图片。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0021"
down_revision = "20260816_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("retail_skus", sa.Column("remark", sa.Text()))
    op.add_column(
        "retail_skus",
        sa.Column("image_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("retail_skus", "image_urls")
    op.drop_column("retail_skus", "remark")
