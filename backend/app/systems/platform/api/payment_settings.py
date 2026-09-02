"""场地支付配置 API。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.systems.platform.models.payment_settings import SitePaymentSettings
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.payment_settings import (
    apply_settings_update,
    import_from_env,
    normalize_payment_mode,
    resolve_payment_settings,
    settings_public_dict,
)

router = APIRouter(prefix="/site/payment-settings", tags=["payment-settings"])


class PaymentSettingsUpdateIn(BaseModel):
    mode: str | None = None
    dry_run: bool | None = None
    mp_app_id: str | None = None
    oa_app_id: str | None = None
    mch_id: str | None = None
    mch_serial_no: str | None = None
    platform_serial_no: str | None = None
    notify_url: str | None = None
    h5_return_url: str | None = None
    mp_app_secret: str | None = Field(default=None, description="空表示不修改")
    oa_app_secret: str | None = None
    api_v3_key: str | None = None
    mch_private_key: str | None = None
    platform_public_key: str | None = None


@router.get("")
def get_payment_settings(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payment:config", "*")
    row = db.get(SitePaymentSettings, ctx.site_id)
    effective = resolve_payment_settings(db, ctx.site_id)
    return settings_public_dict(row, effective)


@router.put("")
def put_payment_settings(
    body: PaymentSettingsUpdateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payment:config", "*")
    payload = body.model_dump(exclude_unset=True)
    if "mode" in payload and payload["mode"] is not None:
        mode = normalize_payment_mode(payload["mode"])
        if mode not in {"unconfigured", "mock", "wechat"}:
            raise AppError("invalid_mode", "支付模式仅支持：未配置 / 模拟支付 / 微信支付", status_code=400)
        payload["mode"] = mode
    row = db.get(SitePaymentSettings, ctx.site_id)
    if row is None:
        row = SitePaymentSettings(site_id=ctx.site_id, mode="unconfigured", dry_run=True)
        db.add(row)
        db.flush()
    apply_settings_update(row, data=payload, staff_id=ctx.staff.id)
    write_audit(
        db,
        action="payment_settings.update",
        target_type="site_payment_settings",
        target_id=ctx.site_id,
        summary=f"更新支付配置 mode={row.mode}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    effective = resolve_payment_settings(db, ctx.site_id)
    return settings_public_dict(row, effective)


@router.post("/import-env")
def import_payment_settings_env(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payment:config", "*")
    row = db.get(SitePaymentSettings, ctx.site_id)
    if row is None:
        row = SitePaymentSettings(site_id=ctx.site_id)
        db.add(row)
        db.flush()
    import_from_env(row, staff_id=ctx.staff.id)
    write_audit(
        db,
        action="payment_settings.import_env",
        target_type="site_payment_settings",
        target_id=ctx.site_id,
        summary="从环境变量导入支付配置",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    effective = resolve_payment_settings(db, ctx.site_id)
    return settings_public_dict(row, effective)
