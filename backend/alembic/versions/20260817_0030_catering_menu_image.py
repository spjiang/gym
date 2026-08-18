"""20260817_0030 餐饮菜品图片。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0030"
down_revision = "20260817_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catering_menu_items", sa.Column("image_url", sa.String(length=255), nullable=True))
    op.add_column("catering_menu_items", sa.Column("description", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("catering_menu_items", "description")
    op.drop_column("catering_menu_items", "image_url")
