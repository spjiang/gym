"""会员短信验证码发送与校验。"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.systems.platform.models.otp import MemberOtpChallenge


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_member_otp(db: Session, *, phone: str, member_id: int | None = None) -> str:
    """按手机号发送验证码；未注册也可发（member_id 可空）。"""
    settings = get_settings()
    mode = settings.member_otp_mode.lower()
    if mode == "mock":
        code = settings.member_otp_mock_code
        db.add(
            MemberOtpChallenge(
                member_id=member_id,
                phone=phone,
                code=code,
                expires_at=_now() + timedelta(minutes=10),
            )
        )
        db.flush()
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
        db.add(
            MemberOtpChallenge(
                member_id=member_id,
                phone=phone,
                code=code,
                expires_at=_now() + timedelta(minutes=10),
            )
        )
        db.flush()
        return "验证码已发送"

    raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)


def verify_member_otp(db: Session, *, phone: str, code: str) -> None:
    """按手机号校验验证码。"""
    settings = get_settings()
    mode = settings.member_otp_mode.lower()
    if mode not in {"mock", "http"}:
        raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)

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
