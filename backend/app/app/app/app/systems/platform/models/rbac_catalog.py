"""RBAC 能力目录与角色装配表。"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.systems.platform.models.identity import JSONType


class Subsystem(Base):
    __tablename__ = "subsystems"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))
    is_business: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PermissionDef(Base):
    __tablename__ = "permission_defs"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    subsystem_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("subsystems.code"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MenuDef(Base):
    __tablename__ = "menu_defs"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    subsystem_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("subsystems.code"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    required_any: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_code", name="uq_role_permission"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    permission_code: Mapped[str] = mapped_column(String(64), nullable=False)


class RoleMenu(Base):
    __tablename__ = "role_menus"
    __table_args__ = (UniqueConstraint("role_id", "menu_code", name="uq_role_menu"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    menu_code: Mapped[str] = mapped_column(String(64), nullable=False)
