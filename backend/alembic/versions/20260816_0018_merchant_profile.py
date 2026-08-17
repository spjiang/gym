"""20260816_0018 商户基础档案与联系人。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0018"
down_revision = "20260816_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("merchants", sa.Column("legal_name", sa.String(128)))
    op.add_column("merchants", sa.Column("credit_code", sa.String(32)))
    op.add_column("merchants", sa.Column("license_no", sa.String(64)))
    op.add_column("merchants", sa.Column("license_image_url", sa.String(512)))
    op.add_column("merchants", sa.Column("legal_person", sa.String(64)))
    op.add_column("merchants", sa.Column("registered_address", sa.String(255)))
    op.add_column("merchants", sa.Column("business_address", sa.String(255)))
    op.add_column("merchants", sa.Column("contact_phone", sa.String(32)))
    op.add_column("merchants", sa.Column("contact_email", sa.String(128)))
    op.add_column("merchants", sa.Column("business_hours", sa.String(128)))
    op.add_column("merchants", sa.Column("description", sa.Text()))
    op.create_table(
        "merchant_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("title", sa.String(64)),
        sa.Column("kind", sa.String(16), nullable=False, server_default="other"),
        sa.Column("remark", sa.String(255)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_merchant_contacts_merchant_id", "merchant_contacts", ["merchant_id"])


def downgrade() -> None:
    op.drop_index("ix_merchant_contacts_merchant_id", table_name="merchant_contacts")
    op.drop_table("merchant_contacts")
    op.drop_column("merchants", "description")
    op.drop_column("merchants", "business_hours")
    op.drop_column("merchants", "contact_email")
    op.drop_column("merchants", "contact_phone")
    op.drop_column("merchants", "business_address")
    op.drop_column("merchants", "registered_address")
    op.drop_column("merchants", "legal_person")
    op.drop_column("merchants", "license_image_url")
    op.drop_column("merchants", "license_no")
    op.drop_column("merchants", "credit_code")
    op.drop_column("merchants", "legal_name")
