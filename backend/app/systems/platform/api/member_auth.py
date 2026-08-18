"""会员验证码登录（支持扫码注册与商户挂靠）。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import MemberContext, get_current_member
from app.core.errors import AppError
from app.core.schemas.common import TokenOut
from app.core.security import create_access_token, verify_password
from app.systems.platform.models.member import AcquisitionSource, FaceStatus, Member, MerchantMember
from app.systems.platform.models.org import Merchant, MerchantStatus, Site
from app.systems.platform.models.payment_settings import MemberWechatBinding
from app.systems.platform.models.promoter import PromoterCode
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.otp import send_member_otp, verify_member_otp
from app.systems.platform.services.payment_settings import resolve_payment_settings
from app.systems.platform.services.promotion import ensure_member_promoter_code
from app.systems.platform.services.wechat_pay import exchange_mini_openid, exchange_oa_openid

router = APIRouter(prefix="/member/auth", tags=["member-auth"])


class OtpSendIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    merchant_id: int | None = None


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    code: str = Field(min_length=4, max_length=16)
    merchant_id: int | None = None
    # 推广码：仅首次注册时落库，老会员不覆盖既有推荐关系
    referral_code: str | None = Field(default=None, max_length=32)


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


def _resolve_promoter(db: Session, code: str | None, *, site_id: int) -> PromoterCode | None:
    """解析推广码；无效或停用时静默忽略，不阻断注册。"""
    normalized = (code or "").strip().upper()
    if not normalized:
        return None
    promoter = db.scalar(select(PromoterCode).where(PromoterCode.code == normalized))
    if promoter is None or promoter.site_id != site_id or not promoter.is_active:
        return None
    return promoter


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
        promoter = _resolve_promoter(db, body.referral_code, site_id=site.id)
        member = Member(
            site_id=site.id,
            phone=body.phone,
            name=f"会员{body.phone[-4:]}",
            face_status=FaceStatus.NOT_ENROLLED.value,
            acquisition_source=src,
            first_merchant_id=merchant.id if merchant else None,
            referral_code=promoter.code if promoter else None,
            referrer_member_id=promoter.subject_member_id if promoter else None,
        )
        db.add(member)
        db.flush()
        ensure_member_promoter_code(db, member)
        if merchant is not None:
            _ensure_link(db, member_id=member.id, merchant_id=merchant.id)
        write_audit(
            db,
            action="member.register",
            target_type="member",
            target_id=member.id,
            summary=(
                f"会员自助注册 source={src}"
                + (f" 推广码={promoter.code}" if promoter else "")
            ),
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


class PasswordLoginIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=1, max_length=64)
    merchant_id: int | None = None


@router.post("/password", response_model=TokenOut)
def login_with_password(body: PasswordLoginIn, db: Session = Depends(get_db)):
    """已设置密码的会员可用手机号+密码登录；未设置则需走验证码。"""
    member = db.scalar(select(Member).where(Member.phone == body.phone.strip()))
    if member is None or not member.password_hash or not verify_password(body.password, member.password_hash):
        raise AppError("invalid_credentials", "手机号或密码错误", status_code=401)

    merchant = _resolve_merchant(db, body.merchant_id, site_id=member.site_id)
    if merchant is not None:
        linked = _ensure_link(db, member_id=member.id, merchant_id=merchant.id)
        if linked:
            write_audit(
                db,
                action="member.link_merchant",
                target_type="member",
                target_id=member.id,
                summary=f"密码登录挂靠商户 merchant_id={merchant.id}",
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
        summary="会员密码登录成功",
        site_id=member.site_id,
        merchant_id=body.merchant_id,
    )
    db.commit()
    return TokenOut(access_token=token)


class WechatBindIn(BaseModel):
    code: str = Field(min_length=1, max_length=128)


@router.post("/wechat/mini/bind")
def bind_mini_openid(
    body: WechatBindIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """登录后绑定小程序 openid。"""
    cfg = resolve_payment_settings(db, mctx.site_id)
    openid = exchange_mini_openid(cfg, body.code)
    row = db.scalar(select(MemberWechatBinding).where(MemberWechatBinding.member_id == mctx.member.id))
    if row is None:
        row = MemberWechatBinding(member_id=mctx.member.id)
        db.add(row)
    row.mp_openid = openid
    db.commit()
    return {"mp_openid": openid, "bound": True}


@router.post("/wechat/oa/bind")
def bind_oa_openid(
    body: WechatBindIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """登录后绑定公众号/网页 openid。"""
    cfg = resolve_payment_settings(db, mctx.site_id)
    openid = exchange_oa_openid(cfg, body.code)
    row = db.scalar(select(MemberWechatBinding).where(MemberWechatBinding.member_id == mctx.member.id))
    if row is None:
        row = MemberWechatBinding(member_id=mctx.member.id)
        db.add(row)
    row.oa_openid = openid
    db.commit()
    return {"oa_openid": openid, "bound": True}
