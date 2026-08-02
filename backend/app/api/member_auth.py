"""会员验证码登录。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.models.member import Member
from app.schemas.common import TokenOut
from app.security import create_access_token
from app.services.audit import write_audit
from app.services.otp import send_member_otp, verify_member_otp

router = APIRouter(prefix="/member/auth", tags=["member-auth"])


class OtpSendIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    code: str = Field(min_length=4, max_length=16)


class OtpSendOut(BaseModel):
    sent: bool
    message: str


@router.post("/otp/send", response_model=OtpSendOut)
def send_otp(body: OtpSendIn, db: Session = Depends(get_db)):
    settings = get_settings()
    member = db.scalar(select(Member).where(Member.phone == body.phone))
    if member is None:
        raise AppError("member_not_found", "请到前台开卡后再登录", status_code=404)
    # 兼容旧开关：mock 关闭且 mode 仍为 mock 时拒绝
    if settings.member_otp_mode.lower() == "mock" and not settings.member_otp_mock_enabled:
        raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)
    message = send_member_otp(db, member_id=member.id, phone=body.phone)
    write_audit(
        db,
        action="member.otp_send",
        target_type="member",
        target_id=member.id,
        summary=f"发送登录验证码 phone={body.phone}",
        site_id=member.site_id,
    )
    db.commit()
    return OtpSendOut(sent=True, message=message)


@router.post("/otp/verify", response_model=TokenOut)
def verify_otp(body: OtpVerifyIn, db: Session = Depends(get_db)):
    settings = get_settings()
    member = db.scalar(select(Member).where(Member.phone == body.phone))
    if member is None:
        raise AppError("member_not_found", "请到前台开卡后再登录", status_code=404)
    if settings.member_otp_mode.lower() == "mock" and not settings.member_otp_mock_enabled:
        raise AppError("otp_unavailable", "验证码通道未配置", status_code=503)
    verify_member_otp(db, member_id=member.id, phone=body.phone, code=body.code)

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
    )
    db.commit()
    return TokenOut(access_token=token)
