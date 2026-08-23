"""购买协议：场景常量、正文清洗、启用校验。"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.agreement import LegalAgreement
from app.systems.platform.models.org import Merchant

AGREEMENT_SCENES = ("membership", "pt_package", "activity", "dining")

_SCRIPT_RE = re.compile(r"<(script|iframe|object|embed)[\s\S]*?>[\s\S]*?</\1>", re.IGNORECASE)
_EVENT_RE = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)


def sanitize_agreement_html(raw: str) -> str:
    text = (raw or "").strip()
    text = _SCRIPT_RE.sub("", text)
    text = _EVENT_RE.sub("", text)
    return text


def assert_scene(scene: str) -> str:
    value = (scene or "").strip()
    if value not in AGREEMENT_SCENES:
        raise AppError("invalid_scene", "未知协议场景", status_code=422)
    return value


def require_enabled_agreement(db: Session, *, merchant_id: int, scene: str) -> LegalAgreement:
    """会员下单前必须存在该商户该场景的启用协议。"""
    scene = assert_scene(scene)
    row = db.scalar(
        select(LegalAgreement).where(
            LegalAgreement.merchant_id == merchant_id,
            LegalAgreement.scene == scene,
            LegalAgreement.is_enabled.is_(True),
        )
    )
    if row is None:
        raise AppError("agreement_required", "该门店尚未配置购买协议，请联系门店", status_code=400)
    return row


def require_merchant_in_site(db: Session, *, merchant_id: int, site_id: int) -> Merchant:
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or merchant.site_id != site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    return merchant
