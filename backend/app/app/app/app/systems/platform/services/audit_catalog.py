"""审计路径规则：推断业务子系统与操作模块。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditRouteMeta:
    subsystem_code: str
    module: str


# 按前缀长度降序匹配，避免 /member 覆盖 /member/catering
AUDIT_ROUTE_RULES: tuple[tuple[str, AuditRouteMeta], ...] = tuple(
    sorted(
        [
            ("/api/v1/member/catering", AuditRouteMeta("catering", "会员餐饮")),
            ("/api/v1/member/promotion", AuditRouteMeta("platform", "会员推广")),
            ("/api/v1/member/auth", AuditRouteMeta("member", "会员认证")),
            ("/api/v1/member", AuditRouteMeta("member", "会员端")),
            ("/api/v1/catering", AuditRouteMeta("catering", "餐饮管理")),
            ("/api/v1/memberships", AuditRouteMeta("gym", "会籍管理")),
            ("/api/v1/membership", AuditRouteMeta("gym", "会籍管理")),
            ("/api/v1/group-", AuditRouteMeta("gym", "团课管理")),
            ("/api/v1/pt-", AuditRouteMeta("gym", "私教管理")),
            ("/api/v1/coach", AuditRouteMeta("gym", "教练管理")),
            ("/api/v1/retail", AuditRouteMeta("gym", "零售管理")),
            ("/api/v1/equipment", AuditRouteMeta("gym", "器材管理")),
            ("/api/v1/activit", AuditRouteMeta("gym", "活动管理")),
            ("/api/v1/commission", AuditRouteMeta("gym", "提成管理")),
            ("/api/v1/sales-reps", AuditRouteMeta("gym", "销售管理")),
            ("/api/v1/coupons", AuditRouteMeta("gym", "优惠券")),
            ("/api/v1/products", AuditRouteMeta("gym", "产品管理")),
            ("/api/v1/orders", AuditRouteMeta("platform", "订单管理")),
            ("/api/v1/members", AuditRouteMeta("platform", "会员管理")),
            ("/api/v1/visits", AuditRouteMeta("platform", "访客管理")),
            ("/api/v1/access", AuditRouteMeta("platform", "门禁管理")),
            ("/api/v1/device", AuditRouteMeta("platform", "门禁设备")),
            ("/api/v1/staff", AuditRouteMeta("platform", "员工管理")),
            ("/api/v1/rbac", AuditRouteMeta("platform", "权限配置")),
            ("/api/v1/merchants", AuditRouteMeta("platform", "商户管理")),
            ("/api/v1/merchant-types", AuditRouteMeta("platform", "商户类型")),
            ("/api/v1/site/", AuditRouteMeta("platform", "场地配置")),
            ("/api/v1/agreements", AuditRouteMeta("platform", "协议管理")),
            ("/api/v1/reports", AuditRouteMeta("platform", "报表中心")),
            ("/api/v1/notifications", AuditRouteMeta("platform", "站内通知")),
            ("/api/v1/promotion", AuditRouteMeta("platform", "推广管理")),
            ("/api/v1/payouts", AuditRouteMeta("platform", "提现管理")),
            ("/api/v1/rebates", AuditRouteMeta("platform", "返点管理")),
            ("/api/v1/uploads", AuditRouteMeta("platform", "文件上传")),
            ("/api/v1/auth", AuditRouteMeta("platform", "管理端认证")),
            ("/api/v1/payments", AuditRouteMeta("platform", "支付回调")),
            ("/api/v1/audit-logs", AuditRouteMeta("platform", "操作日志")),
        ],
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

CLIENT_CHANNEL_LABELS: dict[str, str] = {
    "admin_web": "管理后台",
    "member_h5": "会员 H5",
    "member_mp": "微信小程序",
    "device_pad": "门禁 Pad",
    "webhook": "支付回调",
    "internal": "系统内部",
    "unknown": "未知客户端",
}

SUBSYSTEM_LABELS: dict[str, str] = {
    "platform": "综合平台",
    "gym": "观野FIT",
    "catering": "观野BAR",
    "member": "会员端",
    "device": "门禁设备",
}

SKIP_AUDIT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)

SKIP_AUDIT_PATHS: set[str] = {
    "/api/v1/me/navigation",
    "/api/v1/auth/me",
    "/api/v1/member/me",
}


def resolve_route_meta(path: str) -> AuditRouteMeta:
    for prefix, meta in AUDIT_ROUTE_RULES:
        if path.startswith(prefix):
            return meta
    return AuditRouteMeta("platform", "综合平台")


def should_auto_audit(method: str, path: str) -> bool:
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return False
    if any(path.startswith(p) for p in SKIP_AUDIT_PREFIXES):
        return False
    if path in SKIP_AUDIT_PATHS:
        return False
    if not path.startswith("/api/v1"):
        return False
    return True


def infer_client_channel(
    *,
    header_value: str | None,
    user_agent: str | None,
    has_device_headers: bool,
    token_typ: str | None,
    path: str,
) -> str:
    normalized = (header_value or "").strip().lower()
    if normalized in CLIENT_CHANNEL_LABELS:
        return normalized
    if has_device_headers or path.startswith("/api/v1/device"):
        return "device_pad"
    if path.startswith("/api/v1/payments/"):
        return "webhook"
    ua = (user_agent or "").lower()
    if "miniprogram" in ua or "micromessenger" in ua and "mini" in ua:
        return "member_mp"
    if token_typ == "member":
        return "member_h5"
    if token_typ == "staff" or path.startswith("/api/v1/auth/login"):
        return "admin_web"
    return "unknown"


def sanitize_audit_payload(data: dict | None) -> dict | None:
    if not data:
        return None
    blocked = {"password", "old_password", "new_password", "token", "access_token", "api_key"}
    out: dict = {}
    for key, value in data.items():
        if key.lower() in blocked:
            out[key] = "***"
        elif isinstance(value, dict):
            out[key] = sanitize_audit_payload(value)
        else:
            out[key] = value
    return out


def extract_path_target_id(path: str) -> str:
    nums = re.findall(r"/(\d+)(?:/|$)", path)
    return nums[-1] if nums else "-"
