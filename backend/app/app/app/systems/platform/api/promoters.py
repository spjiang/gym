"""公开推广码解析：会员扫码落地时识别推荐人并累计访问。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.systems.platform.models.org import Merchant
from app.systems.platform.models.promoter import PromoterCode

public_router = APIRouter(prefix="/promotions", tags=["promoter-public"])


class PromotionResolveOut(BaseModel):
    """公开落地页解析结果，不暴露内部主体 id。"""

    code: str
    name: str
    channel: str
    merchant_id: int | None
    merchant_name: str | None
    landing_path: str | None
    is_active: bool


@public_router.get("/{code}", response_model=PromotionResolveOut)
def resolve_promotion(code: str, db: Session = Depends(get_db)):
    """会员端扫码落地：解析推广码并累计访问量。"""
    promoter = db.scalar(select(PromoterCode).where(PromoterCode.code == code.strip().upper()))
    if promoter is None or not promoter.is_active:
        raise AppError("not_found", "推广码无效或已停用", status_code=404)
    promoter.visit_count += 1
    merchant_name = None
    if promoter.merchant_id is not None:
        merchant = db.get(Merchant, promoter.merchant_id)
        merchant_name = merchant.name if merchant else None
    db.commit()
    return PromotionResolveOut(
        code=promoter.code,
        name=promoter.name,
        channel=promoter.channel,
        merchant_id=promoter.merchant_id,
        merchant_name=merchant_name,
        landing_path=promoter.landing_path,
        is_active=promoter.is_active,
    )
