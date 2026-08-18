"""20260818_0032 场地门户展示：口号、介绍、客服电话、广告图。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260818_0032"
down_revision = "20260817_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("tagline", sa.String(length=128), nullable=True))
    op.add_column("sites", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("sites", sa.Column("service_phone", sa.String(length=32), nullable=True))
    op.add_column("sites", sa.Column("business_hours", sa.String(length=128), nullable=True))
    op.add_column("sites", sa.Column("cover_image_url", sa.String(length=255), nullable=True))
    op.add_column(
        "sites",
        sa.Column("banner_image_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "sites",
        sa.Column("gallery_image_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("sites", "gallery_image_urls")
    op.drop_column("sites", "banner_image_urls")
    op.drop_column("sites", "cover_image_url")
    op.drop_column("sites", "business_hours")
    op.drop_column("sites", "service_phone")
    op.drop_column("sites", "description")
    op.drop_column("sites", "tagline")
