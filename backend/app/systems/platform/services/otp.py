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
from app.systems.platform.services.aliyun_sms import call_aliyun_sms
from app.systems.platform.services.sms_log import record_sms_send


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
        access_key_id = decrypt_secret(aliyun.api_key_enc) or ""
        sign_name = aliyun.sign_name or ""
        template_param = {"code": code}
        request_view = {
            "Url": "https://dysmsapi.aliyuncs.com/",
            "Action": "SendSms",
            "Version": "2017-05-25",
            "PhoneNumbers": phone,
            "SignName": sign_name,
            "TemplateCode": template.code,
            "TemplateParam": template_param,
            "AccessKeyId": access_key_id,
        }
        try:
            provider = call_aliyun_sms(
                access_key_id=access_key_id,
                access_key_secret=decrypt_secret(aliyun.api_secret_enc) or "",
                phone=phone,
                sign_name=sign_name,
                template_code=template.code,
                template_param=template_param,
            )
        except AppError as exc:
            record_sms_send(
                site_id=aliyun.site_id,
                phone=phone,
                scene=scene,
                provider="aliyun",
                status="failed",
                template_code=template.code,
                sign_name=sign_name,
                provider_message=exc.message,
                request_json=request_view,
            )
            raise
        sent = provider.get("Code") == "OK"
        record_sms_send(
            site_id=aliyun.site_id,
            phone=phone,
            scene=scene,
            provider="aliyun",
            status="success" if sent else "failed",
            template_code=template.code,
            sign_name=sign_name,
            provider_code=str(provider.get("Code") or "") or None,
            provider_message=str(provider.get("Message") or "") or None,
            request_json=request_view,
            response_json=provider,
        )
        if not sent:
            message = provider.get("Message") or provider.get("Code") or "发送失败"
            raise AppError("otp_send_failed", f"阿里云短信失败: {message}", status_code=502)
        _store_challenge(db, phone=phone, member_id=member_id, code=code)
        return "验证码已发送"

    settings = get_settings()
    mode = settings.member_otp_mode.lower()
    if mode == "mock":
        code = settings.member_otp_mock_code
        record_sms_send(
            site_id=site_id,
            phone=phone,
            scene=scene,
            provider="mock",
            status="success",
            provider_message="开发环境未调用短信网关",
            request_json={"PhoneNumbers": phone, "TemplateParam": {"code": code}},
        )
        _store_challenge(db, phone=phone, member_id=member_id, code=code)
        return "验证码已发送（开发环境请使用配置的 mock 码）"

    if mode == "http":
        if not settings.member_otp_sms_url:
            raise AppError("otp_unavailable", "短信网关未配置 MEMBER_OTP_SMS_URL", status_code=503)
        code = _gen_code()
        request_view = {"PhoneNumbers": phone, "TemplateParam": {"code": code}, "Url": settings.member_otp_sms_url}
        try:
            resp = httpx.post(
                settings.member_otp_sms_url,
                json={"phone": phone, "code": code},
                timeout=10.0,
                headers={"Authorization": settings.member_otp_sms_token or ""},
            )
            if resp.status_code >= 400:
                record_sms_send(
                    site_id=site_id,
                    phone=phone,
                    scene=scene,
                    provider="http",
                    status="failed",
                    provider_code=str(resp.status_code),
                    provider_message=f"短信网关失败: HTTP {resp.status_code}",
                    request_json=request_view,
                )
                raise AppError("otp_send_failed", f"短信网关失败: HTTP {resp.status_code}", status_code=502)
        except httpx.HTTPError as exc:
            record_sms_send(
                site_id=site_id,
                phone=phone,
                scene=scene,
                provider="http",
                status="failed",
                provider_message=f"短信网关不可达: {exc}",
                request_json=request_view,
            )
            raise AppError("otp_send_failed", f"短信网关不可达: {exc}", status_code=502) from exc
        record_sms_send(
            site_id=site_id,
            phone=phone,
            scene=scene,
            provider="http",
            status="success",
            provider_code=str(resp.status_code),
            request_json=request_view,
        )
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
