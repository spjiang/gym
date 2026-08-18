"""20260817_0029 商户店铺展示：封面、口号与环境图。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0029"
down_revision = "20260817_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("merchants", sa.Column("tagline", sa.String(length=64), nullable=True))
    op.add_column("merchants", sa.Column("cover_image_url", sa.String(length=255), nullable=True))
    op.add_column(
        "merchants",
        sa.Column("gallery_image_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("merchants", "gallery_image_urls")
    op.drop_column("merchants", "cover_image_url")
    op.drop_column("merchants", "tagline")
