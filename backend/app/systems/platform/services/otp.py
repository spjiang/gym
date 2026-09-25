"""会员短信验证码发送与校验。"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto_secrets import decrypt_secret
from app.core.errors import AppError
from app.systems.platform.models.otp import MemberOtpChallenge
from app.systems.platform.models.sms import SiteSmsSettings, SmsTemplate
from app.systems.platform.services.aliyun_sms import send_aliyun_sms


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _store_challenge(db: Session, *, phone: str, member_id: int | None, code: str) -> None:
    db.add(
        MemberOtpChallenge(
            member_id=member_id,
            phone=phone,
            code=code,
            expires_at=_now() + timedelta(minutes=10),
        )
    )
    db.flush()


def _aliyun_otp_ready(db: Session, site_id: int | None) -> SiteSmsSettings | None:
    if site_id is None:
        return None
    row = db.get(SiteSmsSettings, site_id)
    if row is None or not row.enabled or (row.provider or "") != "aliyun":
        return None
    if not row.sign_name or not decrypt_secret(row.api_key_enc) or not decrypt_secret(row.api_secret_enc):
        return None
    return row


OTP_SCENES = ("login", "register", "reset", "otp")


def _otp_template(db: Session, *, site_id: int, scene: str) -> SmsTemplate | None:
    """按场景取启用模版；登录/注册/找回没有专属模版时，回退到通用验证码。"""
    wanted = scene if scene in OTP_SCENES else "login"
    template = db.scalar(
        select(SmsTemplate)
        .where(
            SmsTemplate.site_id == site_id,
            SmsTemplate.scene == wanted,
            SmsTemplate.is_enabled.is_(True),
        )
        .order_by(SmsTemplate.id.desc())
    )
    if template is None and wanted != "otp":
        template = db.scalar(
            select(SmsTemplate)
            .where(
                SmsTemplate.site_id == site_id,
                SmsTemplate.scene == "otp",
                SmsTemplate.is_enabled.is_(True),
            )
            .order_by(SmsTemplate.id.desc())
        )
    return template


def send_member_otp(
    db: Session,
    *,
    phone: str,
    member_id: int | None = None,
    site_id: int | None = None,
    scene: str = "login",
) -> str:
    """按手机号发送验证码；未注册也可发（member_id 可空）。"""
    aliyun = _aliyun_otp_ready(db, site_id)
    if aliyun is not None:
        template = _otp_template(db, site_id=aliyun.site_id, scene=scene)
        if template is None:
            raise AppError("otp_unavailable", "请先启用对应场景的短信模版，编码填阿里云模板 CODE", status_code=503)
        code = _gen_code()
        send_aliyun_sms(
            access_key_id=decrypt_secret(aliyun.api_key_enc) or "",
            access_key_secret=decrypt_secret(aliyun.api_secret_enc) or "",
            phone=phone,
            sign_name=aliyun.sign_name or "",
            template_code=template.code,
            template_param={"code": code},
        )
        _store_challenge(db, phone=phone, member_id=member_id, code=code)
        return "验证码已发送"

    settings = get_settings()
    mode = settings.member_otp_mode.lower()
    if mode == "mock":
        code = settings.member_otp_mock_code
        _store_challenge(db, phone=phone, member_id=member_id, code=code)
        return "验证码已发送（开发环境请使用配置的 mock 码）"

    if mode == "http":
        if not settings.member_otp_sms_url:
            raise AppError("otp_unavailable", "短信网关未配置 MEMBER_OTP_SMS_URL", status_code=503)
        code = _gen_code()
        try:
            resp = httpx.post(
                settings.member_otp_sms_url,
                json={"phone": phone, "code": code},
                timeout=10.0,
                headers={"Authorization": settings.member_otp_sms_token or ""},
            )
            if resp.status_code >= 400:
                raise AppError("otp_send_failed", f"短信网关失败: HTTP {resp.status_code}", status_code=502)
        except httpx.HTTPError as exc:
            raise AppError("otp_send_failed", f"短信网关不可达: {exc}", status_code=502) from exc
        _store_challenge(db, phone=phone, member_id=member_id, code=code)
        return "验证码已发送"

    raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)


def verify_member_otp(db: Session, *, phone: str, code: str) -> None:
    """按手机号校验验证码。"""
    settings = get_settings()
    mode = settings.member_otp_mode.lower()
    challenge = db.scalar(
        select(MemberOtpChallenge)
        .where(
            MemberOtpChallenge.phone == phone,
            MemberOtpChallenge.consumed_at.is_(None),
        )
        .order_by(MemberOtpChallenge.id.desc())
    )
    if challenge is None:
        if mode == "mock" and code == settings.member_otp_mock_code:
            return
        raise AppError("invalid_otp", "请先获取验证码", status_code=401)
    exp = challenge.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < _now():
        raise AppError("otp_expired", "验证码已过期", status_code=401)
    if challenge.code != code:
        raise AppError("invalid_otp", "验证码错误", status_code=401)
    challenge.consumed_at = _now()
    db.flush()
