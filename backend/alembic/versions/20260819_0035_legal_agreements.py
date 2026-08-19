"""20260819_0035 会员购买协议。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260819_0035"
down_revision = "20260818_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_agreements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("scene", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("merchant_id", "scene", name="uq_legal_agreement_merchant_scene"),
    )
    op.create_index("ix_legal_agreements_site_id", "legal_agreements", ["site_id"])
    op.create_index("ix_legal_agreements_merchant_id", "legal_agreements", ["merchant_id"])


def downgrade() -> None:
    op.drop_index("ix_legal_agreements_merchant_id", table_name="legal_agreements")
    op.drop_index("ix_legal_agreements_site_id", table_name="legal_agreements")
    op.drop_table("legal_agreements")
