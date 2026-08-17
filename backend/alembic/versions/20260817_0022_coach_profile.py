"""20260817_0022 教练档案扩展：头像、图文介绍与展示字段。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0022"
down_revision = "20260816_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("coaches", sa.Column("title", sa.String(64)))
    op.add_column("coaches", sa.Column("gender", sa.String(16)))
    op.add_column("coaches", sa.Column("phone", sa.String(32)))
    op.add_column("coaches", sa.Column("years_experience", sa.Integer()))
    op.add_column("coaches", sa.Column("hourly_rate", sa.Numeric(12, 2)))
    op.add_column("coaches", sa.Column("certifications", sa.Text()))
    op.add_column("coaches", sa.Column("bio", sa.Text()))
    op.add_column("coaches", sa.Column("avatar_url", sa.String(255)))
    op.add_column(
        "coaches",
        sa.Column("intro_image_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("coaches", "intro_image_urls")
    op.drop_column("coaches", "avatar_url")
    op.drop_column("coaches", "bio")
    op.drop_column("coaches", "certifications")
    op.drop_column("coaches", "hourly_rate")
    op.drop_column("coaches", "years_experience")
    op.drop_column("coaches", "phone")
    op.drop_column("coaches", "gender")
    op.drop_column("coaches", "title")
