"""器材台账迁移。

Revision ID: 20260802_0006
Revises: 20260802_0005
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0006"
down_revision: Union[str, None] = "20260802_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "equipment_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("brand_model", sa.String(128)),
        sa.Column("asset_code", sa.String(64), nullable=False),
        sa.Column("area", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("merchant_id", "asset_code", name="uq_equipment_merchant_code"),
    )
    op.create_index("ix_equipment_assets_merchant_id", "equipment_assets", ["merchant_id"])

    op.create_table(
        "equipment_repair_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("equipment_assets.id"), nullable=False),
        sa.Column("reporter_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("resolution", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_equipment_repair_tickets_merchant_id", "equipment_repair_tickets", ["merchant_id"])
    op.create_index("ix_equipment_repair_tickets_asset_id", "equipment_repair_tickets", ["asset_id"])


def downgrade() -> None:
    op.drop_table("equipment_repair_tickets")
    op.drop_table("equipment_assets")
