"""RBAC 能力目录与角色装配。

部分唯一索引：
- 场地级角色（merchant_id IS NULL）：code 全局唯一
- 商户级角色：同一 merchant_id 下 code 唯一
SQLite / Postgres 均支持 WHERE 部分索引。
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "20260804_0011"
down_revision = "20260804_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subsystems",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("is_business", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deprecated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "permission_defs",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("subsystem_code", sa.String(32), sa.ForeignKey("subsystems.code"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_deprecated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_permission_defs_subsystem_code", "permission_defs", ["subsystem_code"])
    op.create_table(
        "menu_defs",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("subsystem_code", sa.String(32), sa.ForeignKey("subsystems.code"), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("required_any", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deprecated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_menu_defs_subsystem_code", "menu_defs", ["subsystem_code"])

    op.add_column("roles", sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=True))
    op.add_column(
        "roles",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_roles_merchant_id", "roles", ["merchant_id"])

    # 去掉全局 code 唯一，改为部分唯一
    op.drop_constraint("uq_roles_code", "roles", type_="unique")
    op.create_index(
        "uq_roles_site_code",
        "roles",
        ["code"],
        unique=True,
        postgresql_where=sa.text("merchant_id IS NULL"),
        sqlite_where=sa.text("merchant_id IS NULL"),
    )
    op.create_index(
        "uq_roles_merchant_code",
        "roles",
        ["merchant_id", "code"],
        unique=True,
        postgresql_where=sa.text("merchant_id IS NOT NULL"),
        sqlite_where=sa.text("merchant_id IS NOT NULL"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("permission_code", sa.String(64), nullable=False),
        sa.UniqueConstraint("role_id", "permission_code", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_table(
        "role_menus",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("menu_code", sa.String(64), nullable=False),
        sa.UniqueConstraint("role_id", "menu_code", name="uq_role_menu"),
    )
    op.create_index("ix_role_menus_role_id", "role_menus", ["role_id"])

    # 回填 role_permissions；标记 site_admin 为系统角色
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, code, permissions FROM roles")).mappings().all()
    for row in rows:
        perms = row["permissions"]
        if isinstance(perms, str):
            try:
                perms = json.loads(perms)
            except json.JSONDecodeError:
                perms = []
        if not isinstance(perms, list):
            perms = []
        for p in perms:
            if not p:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_code) VALUES (:rid, :p)"
                ),
                {"rid": row["id"], "p": p},
            )
        if row["code"] == "site_admin":
            conn.execute(
                sa.text("UPDATE roles SET is_system = true WHERE id = :id"),
                {"id": row["id"]},
            )


def downgrade() -> None:
    op.drop_table("role_menus")
    op.drop_table("role_permissions")
    op.drop_index("uq_roles_merchant_code", table_name="roles")
    op.drop_index("uq_roles_site_code", table_name="roles")
    op.drop_index("ix_roles_merchant_id", table_name="roles")
    op.drop_column("roles", "is_system")
    op.drop_column("roles", "merchant_id")
    op.create_unique_constraint("uq_roles_code", "roles", ["code"])
    op.drop_table("menu_defs")
    op.drop_table("permission_defs")
    op.drop_table("subsystems")
