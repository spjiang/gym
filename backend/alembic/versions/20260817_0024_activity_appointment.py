"""20260817_0024 活动报名与私教一对一预约。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260817_0024"
down_revision = "20260817_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64)),
        sa.Column("location", sa.String(128)),
        sa.Column("cover_url", sa.String(255)),
        sa.Column("description", sa.Text()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("register_ends_at", sa.DateTime(timezone=True)),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("member_price", sa.Numeric(12, 2)),
        sa.Column("requires_payment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activities_merchant_id", "activities", ["merchant_id"])

    op.create_table(
        "activity_registrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id")),
        sa.Column("checked_in_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("activity_id", "member_id", name="uq_activity_registration_member"),
    )
    op.create_index("ix_activity_registrations_activity_id", "activity_registrations", ["activity_id"])
    op.create_index("ix_activity_registrations_merchant_id", "activity_registrations", ["merchant_id"])
    op.create_index("ix_activity_registrations_member_id", "activity_registrations", ["member_id"])
    op.create_index("ix_activity_registrations_order_id", "activity_registrations", ["order_id"])

    op.create_table(
        "pt_appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("coaches.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("pt_packages.id")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="booked"),
        sa.Column("location", sa.String(128)),
        sa.Column("note", sa.String(255)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pt_appointments_merchant_id", "pt_appointments", ["merchant_id"])
    op.create_index("ix_pt_appointments_member_id", "pt_appointments", ["member_id"])
    op.create_index("ix_pt_appointments_coach_id", "pt_appointments", ["coach_id"])
    op.create_index("ix_pt_appointments_package_id", "pt_appointments", ["package_id"])
    op.create_index("ix_pt_appointments_starts_at", "pt_appointments", ["starts_at"])


def downgrade() -> None:
    op.drop_index("ix_pt_appointments_starts_at", table_name="pt_appointments")
    op.drop_index("ix_pt_appointments_package_id", table_name="pt_appointments")
    op.drop_index("ix_pt_appointments_coach_id", table_name="pt_appointments")
    op.drop_index("ix_pt_appointments_member_id", table_name="pt_appointments")
    op.drop_index("ix_pt_appointments_merchant_id", table_name="pt_appointments")
    op.drop_table("pt_appointments")

    op.drop_index("ix_activity_registrations_order_id", table_name="activity_registrations")
    op.drop_index("ix_activity_registrations_member_id", table_name="activity_registrations")
    op.drop_index("ix_activity_registrations_merchant_id", table_name="activity_registrations")
    op.drop_index("ix_activity_registrations_activity_id", table_name="activity_registrations")
    op.drop_table("activity_registrations")

    op.drop_index("ix_activities_merchant_id", table_name="activities")
    op.drop_table("activities")
