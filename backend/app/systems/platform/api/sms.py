"""短信 API 与模版配置。"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto_secrets import decrypt_secret, encrypt_secret
from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.systems.platform.models.sms import SiteSmsSettings, SmsTemplate
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/site/sms", tags=["sms"])


class SmsSettingsOut(BaseModel):
    provider: str
    api_base_url: str
    sign_name: str
    enabled: bool
    api_key: dict
    api_secret: dict


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
    content: str = Field(min_length=1)
    scene: str = "otp"
    is_enabled: bool = True


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
            api_key={"configured": False},
            api_secret={"configured": False},
        )
    return SmsSettingsOut(
        provider=row.provider or "http",
        api_base_url=row.api_base_url or "",
        sign_name=row.sign_name or "",
        enabled=bool(row.enabled),
        api_key={"configured": bool(decrypt_secret(row.api_key_enc))},
        api_secret={"configured": bool(decrypt_secret(row.api_secret_enc))},
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
