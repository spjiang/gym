"""请求依赖：鉴权、商户隔离、设备凭证。"""

from dataclasses import dataclass

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.errors import AppError
from app.systems.platform.models.access import AccessDevice
from app.systems.platform.models.identity import StaffRole, StaffUser
from app.systems.platform.models.member import Member, MerchantMember
from app.core.security import decode_access_token, verify_device_api_key

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_SITE_ADMIN = "site_admin"
ROLE_MERCHANT_ADMIN = "gym_admin"
ROLE_FRONT_DESK = "gym_ops"
ROLE_COACH = "gym_coach"
ROLE_COACH_LEGACY = "coach"


@dataclass
class RequestContext:
    staff: StaffUser
    site_id: int
    merchant_id: int | None
    role_codes: set[str]
    permissions: set[str]
    site_scoped: bool = False

    @property
    def is_site_admin(self) -> bool:
        return ROLE_SITE_ADMIN in self.role_codes

    @property
    def is_site_wide(self) -> bool:
        """场地超管或场地运营：可按场地查看全部商户，写操作仍受权限约束。"""
        return self.is_site_admin or self.site_scoped

    @property
    def can_reset_account_password(self) -> bool:
        """场地超管，或具备员工管理权限的业务系统超管，可改他人密码。"""
        if self.is_site_admin:
            return True
        return "staff:manage" in self.permissions

    def require_password_reset(self) -> None:
        if not self.can_reset_account_password:
            raise AppError("forbidden", "仅超管可修改账号密码", status_code=403)

    def require_permission(self, *perms: str) -> None:
        if self.is_site_admin:
            return
        if not any(p in self.permissions for p in perms):
            raise AppError("forbidden", "权限不足", status_code=403)

    def resolve_merchant_id(self, requested: int | None = None, *, required: bool = True) -> int | None:
        """非超管强制本商户；超管可指定商户。

        required=False 时场地级账号可不传商户，表示「全部商户」列表筛选。
        """
        if self.is_site_wide:
            mid = requested if requested is not None else self.merchant_id
            if mid is None and required:
                raise AppError("merchant_required", "请指定 merchant_id", status_code=400)
            return mid
        if self.merchant_id is None:
            raise AppError("merchant_required", "当前账号未绑定商户", status_code=403)
        if requested is not None and requested != self.merchant_id:
            raise AppError("forbidden", "禁止跨商户访问", status_code=403)
        return self.merchant_id

    def assert_merchant_access(self, merchant_id: int) -> None:
        """非场地级账号只能操作本商户。"""
        if self.is_site_wide:
            return
        if self.merchant_id != merchant_id:
            raise AppError("forbidden", "禁止跨商户访问", status_code=403)


@dataclass
class MemberContext:
    member: Member
    site_id: int

    def require_merchant(self, db: Session, merchant_id: int) -> int:
        link = db.scalar(
            select(MerchantMember).where(
                MerchantMember.member_id == self.member.id,
                MerchantMember.merchant_id == merchant_id,
            )
        )
        if link is None:
            raise AppError("forbidden", "未关联该商户", status_code=403)
        return merchant_id


def get_current_context(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> RequestContext:
    if creds is None or not creds.credentials:
        raise AppError("unauthorized", "未登录或令牌缺失", status_code=401)
    try:
        payload = decode_access_token(creds.credentials)
    except ValueError as exc:
        raise AppError("unauthorized", str(exc), status_code=401) from exc

    if payload.get("typ") == "member":
        raise AppError("unauthorized", "会员令牌不可访问管理接口", status_code=401)

    staff_id = int(payload["sub"])
    staff = db.scalar(
        select(StaffUser)
        .options(selectinload(StaffUser.roles).selectinload(StaffRole.role))
        .where(StaffUser.id == staff_id)
    )
    if staff is None or not staff.is_active:
        raise AppError("unauthorized", "账号不存在或已停用", status_code=401)

    role_codes: set[str] = set()
    permissions: set[str] = set()
    site_scoped = False
    for sr in staff.roles:
        role_codes.add(sr.role.code)
        site_scoped = site_scoped or bool(sr.role.is_site_scope)
        # 优先读规范表；无 grants 时回退 JSON
        from app.systems.platform.models.rbac_catalog import RolePermission

        grant_rows = list(
            db.scalars(
                select(RolePermission.permission_code).where(RolePermission.role_id == sr.role.id)
            ).all()
        )
        if grant_rows:
            for p in grant_rows:
                permissions.add(p)
        else:
            for p in sr.role.permissions or []:
                permissions.add(p)

    return RequestContext(
        staff=staff,
        site_id=staff.site_id,
        merchant_id=staff.merchant_id,
        role_codes=role_codes,
        permissions=permissions,
        site_scoped=site_scoped,
    )


def get_current_member(
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> MemberContext:
    if creds is None or not creds.credentials:
        raise AppError("unauthorized", "未登录或令牌缺失", status_code=401)
    try:
        payload = decode_access_token(creds.credentials)
    except ValueError as exc:
        raise AppError("unauthorized", str(exc), status_code=401) from exc

    if payload.get("typ") != "member":
        raise AppError("unauthorized", "需要会员令牌", status_code=401)

    member_id = int(payload["sub"])
    member = db.get(Member, member_id)
    if member is None:
        raise AppError("unauthorized", "会员不存在", status_code=401)
    return MemberContext(member=member, site_id=member.site_id)


def get_device(
    db: Session = Depends(get_db),
    x_device_code: str = Header(..., alias="X-Device-Code"),
    x_device_key: str = Header(..., alias="X-Device-Key"),
) -> AccessDevice:
    device = db.scalar(select(AccessDevice).where(AccessDevice.device_code == x_device_code))
    if device is None or not verify_device_api_key(x_device_key, device.api_key_hash):
        raise AppError("device_unauthorized", "设备凭证无效", status_code=401)
    return device
