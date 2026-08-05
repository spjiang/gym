"""会员验证码登录（支持扫码注册与商户挂靠）。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.schemas.common import TokenOut
from app.core.security import create_access_token
from app.systems.platform.models.member import AcquisitionSource, FaceStatus, Member, MerchantMember
from app.systems.platform.models.org import Merchant, MerchantStatus, Site
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.otp import send_member_otp, verify_member_otp

router = APIRouter(prefix="/member/auth", tags=["member-auth"])


class OtpSendIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    merchant_id: int | None = None


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    code: str = Field(min_length=4, max_length=16)
    merchant_id: int | None = None


class OtpSendOut(BaseModel):
    sent: bool
    message: str


def _resolve_merchant(db: Session, merchant_id: int | None, *, site_id: int | None = None) -> Merchant | None:
    if merchant_id is None:
        return None
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or merchant.status != MerchantStatus.ACTIVE.value:
        raise AppError("not_found", "商户不存在或未启用", status_code=404)
    if site_id is not None and merchant.site_id != site_id:
        raise AppError("forbidden", "商户不属于当前场地", status_code=403)
    return merchant


def _ensure_link(db: Session, *, member_id: int, merchant_id: int) -> bool:
    """挂靠商户；返回是否新建关联。"""
    exists = db.scalar(
        select(MerchantMember).where(
            MerchantMember.merchant_id == merchant_id,
            MerchantMember.member_id == member_id,
        )
    )
    if exists is not None:
        return False
    db.add(MerchantMember(merchant_id=merchant_id, member_id=member_id))
    db.flush()
    return True


@router.post("/otp/send", response_model=OtpSendOut)
def send_otp(body: OtpSendIn, db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.member_otp_mode.lower() == "mock" and not settings.member_otp_mock_enabled:
        raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)
    # 可选校验商户，避免无效码浪费短信
    if body.merchant_id is not None:
        _resolve_merchant(db, body.merchant_id)

    member = db.scalar(select(Member).where(Member.phone == body.phone))
    message = send_member_otp(db, phone=body.phone, member_id=member.id if member else None)
    write_audit(
        db,
        action="member.otp_send",
        target_type="member",
        target_id=member.id if member else body.phone,
        summary=f"发送登录验证码 phone={body.phone}",
        site_id=member.site_id if member else None,
        merchant_id=body.merchant_id,
    )
    db.commit()
    return OtpSendOut(sent=True, message=message)


@router.post("/otp/verify", response_model=TokenOut)
def verify_otp(body: OtpVerifyIn, db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.member_otp_mode.lower() == "mock" and not settings.member_otp_mock_enabled:
        raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)

    verify_member_otp(db, phone=body.phone, code=body.code)
    member = db.scalar(select(Member).where(Member.phone == body.phone))
    merchant = _resolve_merchant(
        db,
        body.merchant_id,
        site_id=member.site_id if member else None,
    )

    if member is None:
        site = db.scalar(select(Site).order_by(Site.id.asc()))
        if site is None:
            raise AppError("misconfigured", "场地未初始化", status_code=500)
        if merchant is not None and merchant.site_id != site.id:
            raise AppError("forbidden", "商户不属于当前场地", status_code=403)
        src = AcquisitionSource.MERCHANT.value if merchant else AcquisitionSource.PLATFORM.value
        member = Member(
            site_id=site.id,
            phone=body.phone,
            name=f"会员{body.phone[-4:]}",
            face_status=FaceStatus.NOT_ENROLLED.value,
            acquisition_source=src,
            first_merchant_id=merchant.id if merchant else None,
        )
        db.add(member)
        db.flush()
        if merchant is not None:
            _ensure_link(db, member_id=member.id, merchant_id=merchant.id)
        write_audit(
            db,
            action="member.register",
            target_type="member",
            target_id=member.id,
            summary=f"会员自助注册 source={src}",
            site_id=member.site_id,
            merchant_id=merchant.id if merchant else None,
        )
    else:
        if merchant is not None:
            if merchant.site_id != member.site_id:
                raise AppError("forbidden", "商户不属于当前场地", status_code=403)
            linked = _ensure_link(db, member_id=member.id, merchant_id=merchant.id)
            if linked:
                write_audit(
                    db,
                    action="member.link_merchant",
                    target_type="member",
                    target_id=member.id,
                    summary=f"扫码挂靠商户 merchant_id={merchant.id}",
                    site_id=member.site_id,
                    merchant_id=merchant.id,
                )

    token = create_access_token(
        subject=str(member.id),
        extra={"site_id": member.site_id, "typ": "member"},
    )
    write_audit(
        db,
        action="member.login",
        target_type="member",
        target_id=member.id,
        summary="会员验证码登录成功",
        site_id=member.site_id,
        merchant_id=body.merchant_id,
    )
    db.commit()
    return TokenOut(access_token=token)
