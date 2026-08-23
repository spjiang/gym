"""解析场地有效支付配置（库优先，env 兜底）。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto_secrets import decrypt_secret, encrypt_secret
from app.systems.platform.models.payment_settings import SitePaymentSettings

# 历史误标的 jdpay 与 wechat 同为微信支付 APIv3
_WECHAT_MODE_ALIASES = frozenset({"wechat", "jdpay"})


def normalize_payment_mode(mode: str | None) -> str:
    """归一化支付模式；历史 jdpay 统一视为 wechat。"""
    value = (mode or "unconfigured").strip().lower() or "unconfigured"
    if value in _WECHAT_MODE_ALIASES:
        return "wechat"
    if value in {"mock", "unconfigured"}:
        return value
    return value


def is_wechat_payment_mode(mode: str | None) -> bool:
    return normalize_payment_mode(mode) == "wechat"


@dataclass
class EffectivePaymentSettings:
    mode: str
    dry_run: bool
    mp_app_id: str
    mp_app_secret: str
    oa_app_id: str
    oa_app_secret: str
    mch_id: str
    api_v3_key: str
    mch_serial_no: str
    mch_private_key: str
    notify_url: str
    h5_return_url: str
    source: str  # db | env


def resolve_payment_settings(db: Session, site_id: int) -> EffectivePaymentSettings:
    row = db.get(SitePaymentSettings, site_id)
    env = get_settings()
    if row is not None and row.mode and row.mode != "unconfigured":
        return EffectivePaymentSettings(
            mode=normalize_payment_mode(row.mode),
            dry_run=bool(row.dry_run),
            mp_app_id=row.mp_app_id or env.wechat_app_id or "",
            mp_app_secret=decrypt_secret(row.mp_app_secret_enc) or "",
            oa_app_id=row.oa_app_id or row.mp_app_id or env.wechat_app_id or "",
            oa_app_secret=decrypt_secret(row.oa_app_secret_enc) or "",
            mch_id=row.mch_id or env.wechat_mch_id or "",
            api_v3_key=decrypt_secret(row.api_v3_key_enc) or env.wechat_api_key or "",
            mch_serial_no=row.mch_serial_no or "",
            mch_private_key=decrypt_secret(row.mch_private_key_enc) or "",
            notify_url=row.notify_url or env.wechat_notify_url or "",
            h5_return_url=row.h5_return_url or env.member_web_public_url or "",
            source="db",
        )
    return EffectivePaymentSettings(
        mode=normalize_payment_mode(env.online_payment_mode),
        dry_run=bool(env.wechat_dry_run),
        mp_app_id=env.wechat_app_id or "",
        mp_app_secret="",
        oa_app_id=env.wechat_app_id or "",
        oa_app_secret="",
        mch_id=env.wechat_mch_id or "",
        api_v3_key=env.wechat_api_key or "",
        mch_serial_no="",
        mch_private_key="",
        notify_url=env.wechat_notify_url or "",
        h5_return_url=env.member_web_public_url or "",
        source="env",
    )


def mask_secret(configured: bool) -> dict:
    return {"configured": configured}


def settings_public_dict(row: SitePaymentSettings | None, effective: EffectivePaymentSettings) -> dict:
    return {
        "mode": effective.mode,
        "dry_run": effective.dry_run,
        "source": effective.source,
        "mp_app_id": effective.mp_app_id,
        "oa_app_id": effective.oa_app_id,
        "mch_id": effective.mch_id,
        "mch_serial_no": effective.mch_serial_no,
        "notify_url": effective.notify_url,
        "h5_return_url": effective.h5_return_url,
        "mp_app_secret": mask_secret(bool(row and row.mp_app_secret_enc) or bool(effective.mp_app_secret)),
        "oa_app_secret": mask_secret(bool(row and row.oa_app_secret_enc) or bool(effective.oa_app_secret)),
        "api_v3_key": mask_secret(bool(row and row.api_v3_key_enc) or bool(effective.api_v3_key)),
        "mch_private_key": mask_secret(bool(row and row.mch_private_key_enc) or bool(effective.mch_private_key)),
    }


def apply_settings_update(
    row: SitePaymentSettings,
    *,
    data: dict,
    staff_id: int | None,
) -> None:
    """部分更新；密钥字段空串表示不修改。"""
    if "mode" in data and data["mode"] is not None:
        row.mode = normalize_payment_mode(data["mode"])
    if "dry_run" in data and data["dry_run"] is not None:
        row.dry_run = bool(data["dry_run"])
    for plain_key in ("mp_app_id", "oa_app_id", "mch_id", "mch_serial_no", "notify_url", "h5_return_url"):
        if plain_key in data and data[plain_key] is not None:
            setattr(row, plain_key, data[plain_key] or None)
    secret_map = {
        "mp_app_secret": "mp_app_secret_enc",
        "oa_app_secret": "oa_app_secret_enc",
        "api_v3_key": "api_v3_key_enc",
        "mch_private_key": "mch_private_key_enc",
    }
    for src, dest in secret_map.items():
        if src in data and data[src]:
            setattr(row, dest, encrypt_secret(data[src]))
    row.updated_by_staff_id = staff_id


def import_from_env(row: SitePaymentSettings, *, staff_id: int | None) -> None:
    env = get_settings()
    row.mode = normalize_payment_mode(env.online_payment_mode)
    row.dry_run = bool(env.wechat_dry_run)
    row.mp_app_id = env.wechat_app_id or None
    row.oa_app_id = env.wechat_app_id or None
    row.mch_id = env.wechat_mch_id or None
    if env.wechat_api_key:
        row.api_v3_key_enc = encrypt_secret(env.wechat_api_key)
    row.notify_url = env.wechat_notify_url or None
    row.h5_return_url = env.member_web_public_url or None
    row.updated_by_staff_id = staff_id
