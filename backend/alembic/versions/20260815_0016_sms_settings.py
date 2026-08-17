"""20260815_0016 短信通道与模版。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260815_0016"
down_revision = "20260805_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_sms_settings",
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="http"),
        sa.Column("api_base_url", sa.String(512)),
        sa.Column("api_key_enc", sa.Text()),
        sa.Column("api_secret_enc", sa.Text()),
        sa.Column("sign_name", sa.String(64)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
    )
    op.create_table(
        "sms_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("scene", sa.String(32), nullable=False, server_default="otp"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("site_id", "code", name="uq_sms_templates_site_code"),
    )
    op.create_index("ix_sms_templates_site_id", "sms_templates", ["site_id"])


def downgrade() -> None:
    op.drop_index("ix_sms_templates_site_id", table_name="sms_templates")
    op.drop_table("sms_templates")
    op.drop_table("site_sms_settings")
