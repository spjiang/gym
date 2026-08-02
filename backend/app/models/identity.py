"""员工账号与角色。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base

# SQLite 测试兼容：JSON；Postgres 可用 JSONB（通过 JSON 通用类型即可）
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("code", name="uq_roles_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 权限点列表，如 ["org:manage", "member:write"]
    permissions: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    is_site_scope: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class StaffUser(Base):
    __tablename__ = "staff_users"
    __table_args__ = (UniqueConstraint("username", name="uq_staff_users_username"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roles: Mapped[list["StaffRole"]] = relationship(back_populates="staff", cascade="all, delete-orphan")


class StaffRole(Base):
    __tablename__ = "staff_roles"
    __table_args__ = (UniqueConstraint("staff_id", "role_id", name="uq_staff_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff_users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)

    staff: Mapped[StaffUser] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()
