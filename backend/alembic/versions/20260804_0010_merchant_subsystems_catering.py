"""商户子系统与餐饮能力迁移。"""

from alembic import op
import sqlalchemy as sa

revision = "20260804_0010"
down_revision = "20260802_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_subsystems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("system_code", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("merchant_id", "system_code", name="uq_merchant_subsystem"),
    )
    op.create_index("ix_merchant_subsystems_merchant_id", "merchant_subsystems", ["merchant_id"])
    op.create_index("ix_merchant_subsystems_system_code", "merchant_subsystems", ["system_code"])

    op.create_table(
        "catering_menu_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="饮品"),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_catering_menu_items_merchant_id", "catering_menu_items", ["merchant_id"])

    op.create_table(
        "catering_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), sa.ForeignKey("catering_menu_items.id"), nullable=False),
        sa.Column("name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_amount", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_catering_order_items_order_id", "catering_order_items", ["order_id"])

    # 存量商户按类型补关联
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT m.id, mt.code
            FROM merchants m
            JOIN merchant_types mt ON mt.id = m.merchant_type_id
            """
        )
    ).fetchall()
    for merchant_id, type_code in rows:
        system = "gym" if type_code == "gym" else "catering" if type_code == "bar" else None
        if system is None:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO merchant_subsystems (merchant_id, system_code)
                VALUES (:mid, :code)
                ON CONFLICT (merchant_id, system_code) DO NOTHING
                """
            ),
            {"mid": merchant_id, "code": system},
        )


def downgrade() -> None:
    op.drop_table("catering_order_items")
    op.drop_table("catering_menu_items")
    op.drop_table("merchant_subsystems")
