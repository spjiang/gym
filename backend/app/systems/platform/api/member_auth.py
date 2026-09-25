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
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.systems.platform.models.member import AcquisitionSource, FaceStatus, Member, MerchantMember
from app.systems.platform.models.org import Merchant, MerchantStatus, Site
from app.systems.platform.models.payment_settings import MemberWechatBinding, SitePaymentSettings
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
    # login 登录验证码，register 注册，reset 忘记密码
    scene: str = Field(default="login", max_length=32)


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    code: str = Field(min_length=4, max_length=16)
    merchant_id: int | None = None
    # 推广码：仅首次注册时落库，老会员不覆盖既有推荐关系
    referral_code: str | None = Field(default=None, max_length=32)
    wechat_ticket: str | None = Field(default=None, max_length=512)


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


def _first_site(db: Session) -> Site:
    site = db.scalar(select(Site).order_by(Site.id.asc()))
    if site is None:
        raise AppError("misconfigured", "场地未初始化", status_code=500)
    return site


def _openid_from_wechat_ticket(ticket: str | None) -> str | None:
    raw = (ticket or "").strip()
    if not raw:
        return None
    try:
        payload = decode_access_token(raw)
    except ValueError as exc:
        raise AppError("invalid_ticket", "微信登录已过期，请重新点微信登录", status_code=400) from exc
    if payload.get("typ") != "wechat_oa_pending":
        raise AppError("invalid_ticket", "微信登录已过期，请重新点微信登录", status_code=400)
    openid = str(payload.get("sub") or "").strip()
    if not openid:
        raise AppError("invalid_ticket", "微信登录已过期，请重新点微信登录", status_code=400)
    return openid


def _bind_oa_openid(db: Session, *, member_id: int, openid: str) -> None:
    taken = db.scalar(select(MemberWechatBinding).where(MemberWechatBinding.oa_openid == openid))
    if taken is not None and taken.member_id != member_id:
        raise AppError("wechat_bound", "该微信已绑定其他会员", status_code=409)
    row = db.scalar(select(MemberWechatBinding).where(MemberWechatBinding.member_id == member_id))
    if row is None:
        row = MemberWechatBinding(member_id=member_id)
        db.add(row)
    row.oa_openid = openid


def _issue_member_login(
    db: Session,
    member: Member,
    *,
    merchant_id: int | None,
    summary: str,
    wechat_ticket: str | None = None,
) -> TokenOut:
    merchant = _resolve_merchant(db, merchant_id, site_id=member.site_id)
    if merchant is not None:
        linked = _ensure_link(db, member_id=member.id, merchant_id=merchant.id)
        if linked:
            write_audit(
                db,
                action="member.link_merchant",
                target_type="member",
                target_id=member.id,
                summary=f"登录挂靠商户 merchant_id={merchant.id}",
                site_id=member.site_id,
                merchant_id=merchant.id,
            )
    openid = _openid_from_wechat_ticket(wechat_ticket)
    if openid:
        _bind_oa_openid(db, member_id=member.id, openid=openid)
    token = create_access_token(
        subject=str(member.id),
        extra={"site_id": member.site_id, "typ": "member"},
    )
    write_audit(
        db,
        action="member.login",
        target_type="member",
        target_id=member.id,
        summary=summary,
        site_id=member.site_id,
        merchant_id=merchant_id,
    )
    db.commit()
    return TokenOut(access_token=token)


@router.post("/otp/send", response_model=OtpSendOut)
def send_otp(body: OtpSendIn, db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.member_otp_mode.lower() == "mock" and not settings.member_otp_mock_enabled:
        raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)
    # 可选校验商户，避免无效码浪费短信
    if body.merchant_id is not None:
        _resolve_merchant(db, body.merchant_id)

    member = db.scalar(select(Member).where(Member.phone == body.phone))
    site_id = member.site_id if member is not None else None
    if site_id is None:
        site = db.scalar(select(Site).order_by(Site.id.asc()))
        site_id = site.id if site is not None else None
    scene = body.scene if body.scene in {"login", "register", "reset", "otp"} else "login"
    message = send_member_otp(
        db,
        phone=body.phone,
        member_id=member.id if member else None,
        site_id=site_id,
        scene=scene,
    )
    scene_label = {"login": "登录", "register": "注册", "reset": "找回密码", "otp": "验证码"}[scene]
    write_audit(
        db,
        action="member.otp_send",
        target_type="member",
        target_id=member.id if member else body.phone,
        summary=f"发送{scene_label}验证码 phone={body.phone}",
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

    return _issue_member_login(
        db,
        member,
        merchant_id=body.merchant_id,
        summary="会员验证码登录成功",
        wechat_ticket=body.wechat_ticket,
    )


class PasswordLoginIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=1, max_length=64)
    merchant_id: int | None = None
    wechat_ticket: str | None = Field(default=None, max_length=512)


@router.post("/password", response_model=TokenOut)
def login_with_password(body: PasswordLoginIn, db: Session = Depends(get_db)):
    """已设置密码的会员可用手机号+密码登录；未设置则需走验证码。"""
    member = db.scalar(select(Member).where(Member.phone == body.phone.strip()))
    if member is None or not member.password_hash or not verify_password(body.password, member.password_hash):
        raise AppError("invalid_credentials", "手机号或密码错误", status_code=401)

    return _issue_member_login(
        db,
        member,
        merchant_id=body.merchant_id,
        summary="会员密码登录成功",
        wechat_ticket=body.wechat_ticket,
    )


class PasswordWithOtpIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    code: str = Field(min_length=4, max_length=8)
    password: str = Field(min_length=6, max_length=64)
    merchant_id: int | None = None
    referral_code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=128)


def _require_otp_channel() -> None:
    settings = get_settings()
    if settings.member_otp_mode.lower() == "mock" and not settings.member_otp_mock_enabled:
        raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)


def _create_member_from_phone(
    db: Session,
    *,
    phone: str,
    merchant_id: int | None,
    referral_code: str | None,
    name: str | None,
) -> tuple[Member, int | None]:
    """验证码通过后创建会员，规则与验证码登录首次注册一致。"""
    site = db.scalar(select(Site).order_by(Site.id.asc()))
    if site is None:
        raise AppError("misconfigured", "场地未初始化", status_code=500)
    merchant = _resolve_merchant(db, merchant_id, site_id=site.id)
    if merchant is not None and merchant.site_id != site.id:
        raise AppError("forbidden", "商户不属于当前场地", status_code=403)
    src = AcquisitionSource.MERCHANT.value if merchant else AcquisitionSource.PLATFORM.value
    promoter = _resolve_promoter(db, referral_code, site_id=site.id)
    display = (name or "").strip() or f"会员{phone[-4:]}"
    member = Member(
        site_id=site.id,
        phone=phone,
        name=display,
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
        summary=f"会员自助注册 source={src}" + (f" 推广码={promoter.code}" if promoter else ""),
        site_id=member.site_id,
        merchant_id=merchant.id if merchant else None,
    )
    return member, merchant.id if merchant else None


@router.post("/register", response_model=TokenOut)
def register_with_password(body: PasswordWithOtpIn, db: Session = Depends(get_db)):
    """手机号验证码注册并设置登录密码。"""
    _require_otp_channel()
    phone = body.phone.strip()
    verify_member_otp(db, phone=phone, code=body.code.strip())
    member = db.scalar(select(Member).where(Member.phone == phone))
    merchant_id = body.merchant_id
    if member is not None and member.password_hash:
        raise AppError("already_registered", "该手机号已注册，请登录或找回密码", status_code=409)
    if member is None:
        member, merchant_id = _create_member_from_phone(
            db,
            phone=phone,
            merchant_id=body.merchant_id,
            referral_code=body.referral_code,
            name=body.name,
        )
    else:
        display = (body.name or "").strip()
        if display:
            member.name = display
    member.password_hash = hash_password(body.password)
    return _issue_member_login(
        db,
        member,
        merchant_id=merchant_id,
        summary="会员注册并设置密码",
    )


@router.post("/password/reset", response_model=TokenOut)
def reset_password_with_otp(body: PasswordWithOtpIn, db: Session = Depends(get_db)):
    """短信验证码找回并重设登录密码。"""
    _require_otp_channel()
    phone = body.phone.strip()
    verify_member_otp(db, phone=phone, code=body.code.strip())
    member = db.scalar(select(Member).where(Member.phone == phone))
    if member is None:
        raise AppError("not_found", "该手机号尚未注册", status_code=404)
    member.password_hash = hash_password(body.password)
    write_audit(
        db,
        action="member.password_reset",
        target_type="member",
        target_id=member.id,
        summary=f"会员自助找回密码 {member.phone}",
        site_id=member.site_id,
        merchant_id=body.merchant_id,
    )
    return _issue_member_login(
        db,
        member,
        merchant_id=body.merchant_id,
        summary="会员找回密码后登录",
    )


class WechatBindIn(BaseModel):
    code: str = Field(min_length=1, max_length=128)


def _assign_wechat_openid(db: Session, member_id: int, *, field: str, openid: str) -> None:
    """把 openid 挂到当前会员。同一微信号已绑在别人身上时改挂过来，避免唯一约束 500。"""
    column = getattr(MemberWechatBinding, field)
    taken = db.scalar(select(MemberWechatBinding).where(column == openid))
    if taken is not None and taken.member_id == member_id:
        return
    if taken is not None:
        setattr(taken, field, None)
        db.flush()
    row = db.scalar(select(MemberWechatBinding).where(MemberWechatBinding.member_id == member_id))
    if row is None:
        row = MemberWechatBinding(member_id=member_id)
        db.add(row)
    setattr(row, field, openid)


@router.post("/wechat/mini/bind")
def bind_mini_openid(
    body: WechatBindIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """登录后绑定小程序 openid。"""
    cfg = resolve_payment_settings(db, mctx.site_id)
    openid = exchange_mini_openid(cfg, body.code)
    _assign_wechat_openid(db, mctx.member.id, field="mp_openid", openid=openid)
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
    _assign_wechat_openid(db, mctx.member.id, field="oa_openid", openid=openid)
    db.commit()
    return {"oa_openid": openid, "bound": True}


class WechatOaConfigOut(BaseModel):
    oa_app_id: str
    ready: bool


class WechatOaLoginIn(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    merchant_id: int | None = None


class WechatOaLoginOut(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    need_bind: bool = False
    ticket: str | None = None
    message: str | None = None


@router.get("/wechat/oa/config", response_model=WechatOaConfigOut)
def wechat_oa_config(db: Session = Depends(get_db)):
    """会员 H5 拼微信网页授权用，不含密钥。须单独填公众号 AppID，不能用小程序号。"""
    site = _first_site(db)
    row = db.get(SitePaymentSettings, site.id)
    app_id = ((row.oa_app_id if row else None) or "").strip()
    return WechatOaConfigOut(oa_app_id=app_id, ready=bool(app_id))


@router.post("/wechat/oa", response_model=WechatOaLoginOut)
def login_with_wechat_oa(body: WechatOaLoginIn, db: Session = Depends(get_db)):
    """微信内网页授权：已绑定则发 token，未绑定则发待绑票据。"""
    site = _first_site(db)
    cfg = resolve_payment_settings(db, site.id)
    openid = exchange_oa_openid(cfg, body.code)
    row = db.scalar(select(MemberWechatBinding).where(MemberWechatBinding.oa_openid == openid))
    if row is None:
        ticket = create_access_token(
            subject=openid,
            extra={"typ": "wechat_oa_pending", "site_id": site.id},
        )
        return WechatOaLoginOut(
            need_bind=True,
            ticket=ticket,
            message="该微信尚未绑定会员，请用手机号验证一次，验证后自动绑定",
        )
    member = db.get(Member, row.member_id)
    if member is None:
        raise AppError("not_found", "会员不存在", status_code=404)
    issued = _issue_member_login(
        db,
        member,
        merchant_id=body.merchant_id,
        summary="会员微信快捷登录成功",
    )
    return WechatOaLoginOut(access_token=issued.access_token)
