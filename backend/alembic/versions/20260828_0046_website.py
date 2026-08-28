"""官网 CMS 表

Revision ID: 20260828_0046
Revises: 20260822_0045
Create Date: 2026-08-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0046"
down_revision: Union[str, None] = "20260822_0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "website_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("site_json", sa.JSON(), nullable=False),
        sa.Column("home_json", sa.JSON(), nullable=False),
        sa.Column("brands_json", sa.JSON(), nullable=False),
        sa.Column("updated_by_staff_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["updated_by_staff_id"], ["staff_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", name="uq_website_settings_site"),
    )
    op.create_index("ix_website_settings_site_id", "website_settings", ["site_id"])

    op.create_table(
        "website_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("summary", sa.String(255), nullable=True),
        sa.Column("cover_image_url", sa.String(255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("contact_hint", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by_staff_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["updated_by_staff_id"], ["staff_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_website_articles_site_id", "website_articles", ["site_id"])
    op.create_index(
        "ix_website_articles_list",
        "website_articles",
        ["site_id", "channel", "status", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_website_articles_list", table_name="website_articles")
    op.drop_index("ix_website_articles_site_id", table_name="website_articles")
    op.drop_table("website_articles")
    op.drop_index("ix_website_settings_site_id", table_name="website_settings")
    op.drop_table("website_settings")
