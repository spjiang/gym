"""业态子系统目录与商户能力校验（产品级规则，非演示配置）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.org import MerchantSubsystem

# 可挂到商户上的业态子系统（platform 为场地底座，不挂商户）
BUSINESS_SYSTEMS = ("gym", "catering")

SYSTEM_CATALOG: dict[str, dict] = {
    "platform": {
        "code": "platform",
        "name": "综合经营管理系统",
        "short_name": "综合经营",
        "description": "商户组织、员工权限、会员主档、门禁、跨业态订单与报表。",
        "permission": "system:platform",
    },
    "gym": {
        "code": "gym",
        "name": "健身管理平台",
        "short_name": "健身管理",
        "description": "会籍、教练课程、健身零售、优惠券与器材运维。",
        "permission": "system:gym",
    },
    "catering": {
        "code": "catering",
        "name": "餐饮管理系统",
        "short_name": "餐饮管理",
        "description": "清吧/餐饮菜单、点单收款与退款闭环。",
        "permission": "system:catering",
    },
}

# 线下通用建单时，各业态允许的订单类型
ORDER_TYPES_BY_SYSTEM: dict[str, set[str]] = {
    "gym": {"retail", "membership", "pt", "group"},
    "catering": {"dining", "retail"},
}

# 商户类型编码 → 默认业态（创建时可改）
DEFAULT_SYSTEMS_BY_MERCHANT_TYPE: dict[str, list[str]] = {
    "gym": ["gym"],
    "bar": ["catering"],
}

ORDER_TYPE_LABELS = {
    "retail": "零售",
    "membership": "会籍办卡",
    "pt": "私教",
    "group": "团课",
    "dining": "餐饮消费",
    "pt_package": "私教课包",
}


def normalize_subsystem_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return []
    out: list[str] = []
    for c in codes:
        code = (c or "").strip().lower()
        if not code:
            continue
        if code == "platform":
            continue  # 平台底座不挂商户
        if code not in BUSINESS_SYSTEMS:
            raise AppError("invalid_subsystem", f"不支持的子系统: {code}", status_code=400)
        if code not in out:
            out.append(code)
    return out


def merchant_subsystem_codes(db: Session, merchant_id: int) -> list[str]:
    rows = list(
        db.scalars(
            select(MerchantSubsystem.system_code).where(MerchantSubsystem.merchant_id == merchant_id)
        ).all()
    )
    return list(rows)


def replace_merchant_subsystems(db: Session, merchant_id: int, codes: list[str]) -> list[str]:
    codes = normalize_subsystem_codes(codes)
    if not codes:
        raise AppError("validation_error", "商户至少关联一个业态子系统（健身或餐饮）", status_code=422)
    existing = list(
        db.scalars(select(MerchantSubsystem).where(MerchantSubsystem.merchant_id == merchant_id)).all()
    )
    for row in existing:
        db.delete(row)
    db.flush()
    for code in codes:
        db.add(MerchantSubsystem(merchant_id=merchant_id, system_code=code))
    db.flush()
    return codes


def allowed_order_types_for_merchant(db: Session, merchant_id: int) -> set[str]:
    codes = merchant_subsystem_codes(db, merchant_id)
    allowed: set[str] = set()
    for code in codes:
        allowed |= ORDER_TYPES_BY_SYSTEM.get(code, set())
    return allowed


def assert_order_type_allowed(db: Session, merchant_id: int, order_type: str) -> None:
    allowed = allowed_order_types_for_merchant(db, merchant_id)
    if not allowed:
        raise AppError(
            "merchant_no_subsystem",
            "该商户未关联任何业态子系统，无法创建业务订单",
            status_code=400,
        )
    if order_type not in allowed:
        labels = "、".join(ORDER_TYPE_LABELS.get(t, t) for t in sorted(allowed))
        raise AppError(
            "order_type_not_allowed",
            f"当前商户业态不支持该订单类型；可选：{labels}",
            status_code=400,
        )


def assert_merchant_has_system(db: Session, merchant_id: int, system_code: str) -> None:
    codes = merchant_subsystem_codes(db, merchant_id)
    if system_code not in codes:
        raise AppError(
            "subsystem_not_linked",
            f"商户未关联「{SYSTEM_CATALOG.get(system_code, {}).get('short_name', system_code)}」子系统",
            status_code=403,
        )
