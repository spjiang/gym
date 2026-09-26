"""短信 API 与模版配置。"""

import random
import string
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.crypto_secrets import decrypt_secret, encrypt_secret
from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.sms import SiteSmsSettings, SmsSendLog, SmsTemplate
from app.systems.platform.services.aliyun_sms import call_aliyun_sms
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.sms_log import record_sms_send

router = APIRouter(prefix="/site/sms", tags=["sms"])


class SmsSettingsOut(BaseModel):
    provider: str
    api_base_url: str
    sign_name: str
    enabled: bool
    api_key: str
    api_secret: str


class SmsSettingsIn(BaseModel):
    provider: str | None = None
    api_base_url: str | None = None
    sign_name: str | None = None
    enabled: bool | None = None
    api_key: str | None = Field(default=None, description="空表示不修改")
    api_secret: str | None = None


class SmsTemplateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    content: str = ""
    scene: str = "otp"
    is_enabled: bool = True


class SmsTemplateTestIn(BaseModel):
    phone: str = Field(min_length=1, max_length=20)


class SmsTemplateTestOut(BaseModel):
    sent: bool
    code: str
    message: str
    request: dict
    response: dict


class SmsSendLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    scene: str
    provider: str
    template_code: str | None
    sign_name: str | None
    status: str
    provider_code: str | None
    provider_message: str | None
    request_json: dict | None
    response_json: dict | None
    created_at: datetime


class SmsTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    content: str
    scene: str
    is_enabled: bool
    created_at: datetime


def _settings_out(row: SiteSmsSettings | None) -> SmsSettingsOut:
    if row is None:
        return SmsSettingsOut(
            provider="http",
            api_base_url="",
            sign_name="",
            enabled=False,
            api_key="",
            api_secret="",
        )
    return SmsSettingsOut(
        provider=row.provider or "http",
        api_base_url=row.api_base_url or "",
        sign_name=row.sign_name or "",
        enabled=bool(row.enabled),
        api_key=decrypt_secret(row.api_key_enc) or "",
        api_secret=decrypt_secret(row.api_secret_enc) or "",
    )


@router.get("/settings", response_model=SmsSettingsOut)
def get_sms_settings(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sms:config", "*")
    return _settings_out(db.get(SiteSmsSettings, ctx.site_id))


@router.put("/settings", response_model=SmsSettingsOut)
def put_sms_settings(
    body: SmsSettingsIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sms:config", "*")
    row = db.get(SiteSmsSettings, ctx.site_id)
    if row is None:
        row = SiteSmsSettings(site_id=ctx.site_id, provider="http", enabled=False)
        db.add(row)
        db.flush()
    if body.provider is not None:
        row.provider = body.provider.strip() or "http"
    if body.api_base_url is not None:
        row.api_base_url = body.api_base_url.strip() or None
    if body.sign_name is not None:
        row.sign_name = body.sign_name.strip() or None
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.api_key:
        row.api_key_enc = encrypt_secret(body.api_key)
    if body.api_secret:
        row.api_secret_enc = encrypt_secret(body.api_secret)
    row.updated_by_staff_id = ctx.staff.id
    write_audit(
        db,
        action="sms_settings.update",
        target_type="site_sms_settings",
        target_id=ctx.site_id,
        summary=f"更新短信配置 provider={row.provider} enabled={row.enabled}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return _settings_out(row)


@router.get("/templates", response_model=list[SmsTemplateOut])
def list_sms_templates(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sms:config", "*")
    return list(
        db.scalars(select(SmsTemplate).where(SmsTemplate.site_id == ctx.site_id).order_by(SmsTemplate.id)).all()
    )


@router.post("/templates", response_model=SmsTemplateOut)
def create_sms_template(
    body: SmsTemplateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sms:config", "*")
    code = body.code.strip()
    exists = db.scalar(select(SmsTemplate).where(SmsTemplate.site_id == ctx.site_id, SmsTemplate.code == code))
    if exists:
        raise AppError("conflict", "模版编码已存在", status_code=409)
    row = SmsTemplate(
        site_id=ctx.site_id,
        code=code,
        name=body.name.strip(),
        content=body.content.strip(),
        scene=body.scene.strip() or "otp",
        is_enabled=body.is_enabled,
    )
    db.add(row)
    write_audit(
        db,
        action="sms_template.create",
        target_type="sms_template",
        target_id=0,
        summary=f"创建短信模版 {code}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/templates/{template_id}", response_model=SmsTemplateOut)
def patch_sms_template(
    template_id: int,
    body: SmsTemplateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sms:config", "*")
    row = db.get(SmsTemplate, template_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "模版不存在", status_code=404)
    code = body.code.strip()
    other = db.scalar(
        select(SmsTemplate).where(
            SmsTemplate.site_id == ctx.site_id,
            SmsTemplate.code == code,
            SmsTemplate.id != template_id,
        )
    )
    if other:
        raise AppError("conflict", "模版编码已存在", status_code=409)
    row.code = code
    row.name = body.name.strip()
    row.content = body.content.strip()
    row.scene = body.scene.strip() or "otp"
    row.is_enabled = body.is_enabled
    db.commit()
    db.refresh(row)
    return row


@router.post("/templates/{template_id}/test", response_model=SmsTemplateTestOut)
def test_sms_template(
    template_id: int,
    body: SmsTemplateTestIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """用指定模版向手机号发一条验证码，便于核对阿里云模板 CODE 与签名。"""
    ctx.require_permission("sms:config", "*")
    row = db.get(SmsTemplate, template_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "模版不存在", status_code=404)
    phone = "".join(ch for ch in body.phone if ch.isdigit())
    if len(phone) != 11 or not phone.startswith("1"):
        raise AppError("invalid_phone", "请填写 11 位手机号", status_code=400)
    settings = db.get(SiteSmsSettings, ctx.site_id)
    access_key_id = decrypt_secret(settings.api_key_enc) if settings is not None else ""
    access_key_secret = decrypt_secret(settings.api_secret_enc) if settings is not None else ""
    if (
        settings is None
        or (settings.provider or "") != "aliyun"
        or not settings.enabled
        or not (settings.sign_name or "").strip()
        or not access_key_id
        or not access_key_secret
    ):
        raise AppError("sms_not_ready", "请先启用阿里云通道，并填写 AccessKey 与短信签名", status_code=503)
    code = "".join(random.choices(string.digits, k=6))
    sign_name = (settings.sign_name or "").strip()
    template_param = {"code": code}
    request_view = {
        "Url": "https://dysmsapi.aliyuncs.com/",
        "Action": "SendSms",
        "Version": "2017-05-25",
        "RegionId": "cn-hangzhou",
        "PhoneNumbers": phone,
        "SignName": sign_name,
        "TemplateCode": row.code,
        "TemplateParam": template_param,
        "AccessKeyId": access_key_id,
    }
    try:
        provider = call_aliyun_sms(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            phone=phone,
            sign_name=sign_name,
            template_code=row.code,
            template_param=template_param,
        )
    except AppError as exc:
        record_sms_send(
            site_id=ctx.site_id,
            phone=phone,
            scene="test",
            provider="aliyun",
            status="failed",
            template_code=row.code,
            sign_name=sign_name,
            provider_message=exc.message,
            request_json=request_view,
        )
        raise
    sent = provider.get("Code") == "OK"
    record_sms_send(
        site_id=ctx.site_id,
        phone=phone,
        scene="test",
        provider="aliyun",
        status="success" if sent else "failed",
        template_code=row.code,
        sign_name=sign_name,
        provider_code=str(provider.get("Code") or "") or None,
        provider_message=str(provider.get("Message") or "") or None,
        request_json=request_view,
        response_json=provider,
    )
    write_audit(
        db,
        action="sms_template.test",
        target_type="sms_template",
        target_id=row.id,
        summary=f"测试短信模版 {row.code} phone={phone} code={provider.get('Code')}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    provider_message = str(provider.get("Message") or provider.get("Code") or "")
    message = f"已向 {phone} 发送，验证码 {code}" if sent else f"阿里云未发送：{provider_message}"
    return SmsTemplateTestOut(sent=sent, code=code, message=message, request=request_view, response=provider)


@router.get("/logs", response_model=PageOut[SmsSendLogOut])
def list_sms_logs(
    q: str | None = None,
    scene: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """分页检索本场地的短信发送记录。"""
    ctx.require_permission("sms:config", "*")
    stmt = select(SmsSendLog).where(SmsSendLog.site_id == ctx.site_id)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                SmsSendLog.phone.ilike(like),
                SmsSendLog.template_code.ilike(like),
                SmsSendLog.sign_name.ilike(like),
                SmsSendLog.provider_code.ilike(like),
                SmsSendLog.provider_message.ilike(like),
            )
        )
    if scene:
        stmt = stmt.where(SmsSendLog.scene == scene)
    if status:
        stmt = stmt.where(SmsSendLog.status == status)
    rows, total = paginate(db, stmt.order_by(SmsSendLog.id.desc()), page=page, page_size=page_size)
    return PageOut[SmsSendLogOut](
        items=[SmsSendLogOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/templates/{template_id}")
def delete_sms_template(
    template_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sms:config", "*")
    row = db.get(SmsTemplate, template_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "模版不存在", status_code=404)
    db.delete(row)
    db.commit()
    return {"ok": True}
