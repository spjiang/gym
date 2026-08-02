"""课程业态迁移：教练、私教课包、团课。

Revision ID: 20260802_0003
Revises: 20260802_0002
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0003"
down_revision: Union[str, None] = "20260802_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("staff_user_id", sa.Integer(), sa.ForeignKey("staff_users.id"), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("specialties", sa.String(255)),
        sa.Column("availability_note", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_coaches_merchant_id", "coaches", ["merchant_id"])
    op.create_index("ix_coaches_staff_user_id", "coaches", ["staff_user_id"])

    op.create_table(
        "pt_package_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("session_count", sa.Integer(), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        sa.Column("all_coaches", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_pt_package_products_merchant_id", "pt_package_products", ["merchant_id"])

    op.create_table(
        "pt_package_product_coaches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("pt_package_products.id"), nullable=False),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("coaches.id"), nullable=False),
        sa.UniqueConstraint("product_id", "coach_id", name="uq_pt_product_coach"),
    )
    op.create_index("ix_ptppc_product_id", "pt_package_product_coaches", ["product_id"])
    op.create_index("ix_ptppc_coach_id", "pt_package_product_coaches", ["coach_id"])

    op.create_table(
        "pt_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("pt_package_products.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("remaining_sessions", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_pt_packages_merchant_id", "pt_packages", ["merchant_id"])
    op.create_index("ix_pt_packages_member_id", "pt_packages", ["member_id"])
    op.create_index("ix_pt_packages_product_id", "pt_packages", ["product_id"])

    op.create_table(
        "pt_order_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("pt_package_products.id"), nullable=False),
        sa.Column("fulfilled_package_id", sa.Integer(), sa.ForeignKey("pt_packages.id")),
        sa.Column("fulfill_error", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("order_id", name="uq_pt_order_link_order"),
    )
    op.create_index("ix_pt_order_links_order_id", "pt_order_links", ["order_id"])

    op.create_table(
        "group_courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("difficulty", sa.String(32)),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("default_capacity", sa.Integer(), nullable=False),
        sa.Column("book_ahead_minutes", sa.Integer(), nullable=False),
        sa.Column("cancel_ahead_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_group_courses_merchant_id", "group_courses", ["merchant_id"])

    op.create_table(
        "group_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("group_courses.id"), nullable=False),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("coaches.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("room", sa.String(64)),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_group_sessions_merchant_id", "group_sessions", ["merchant_id"])
    op.create_index("ix_group_sessions_course_id", "group_sessions", ["course_id"])
    op.create_index("ix_group_sessions_coach_id", "group_sessions", ["coach_id"])

    op.create_table(
        "group_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("group_sessions.id"), nullable=False),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("session_id", "member_id", name="uq_group_booking_session_member"),
    )
    op.create_index("ix_group_bookings_session_id", "group_bookings", ["session_id"])
    op.create_index("ix_group_bookings_merchant_id", "group_bookings", ["merchant_id"])
    op.create_index("ix_group_bookings_member_id", "group_bookings", ["member_id"])


def downgrade() -> None:
    op.drop_table("group_bookings")
    op.drop_table("group_sessions")
    op.drop_table("group_courses")
    op.drop_table("pt_order_links")
    op.drop_table("pt_packages")
    op.drop_table("pt_package_product_coaches")
    op.drop_table("pt_package_products")
    op.drop_table("coaches")
