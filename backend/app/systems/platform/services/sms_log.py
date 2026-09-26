"""记录平台发出的短信，验证码明文不入库。"""

from __future__ import annotations

import copy
import logging
from typing import Any

from app.core import db as db_module
from app.systems.platform.models.sms import SmsSendLog

logger = logging.getLogger(__name__)


def mask_sms_payload(payload: dict | None) -> dict | None:
    """请求体里的验证码改为星号，避免发送记录可被拿去登录。"""
    if payload is None:
        return None
    data = copy.deepcopy(payload)
    param = data.get("TemplateParam")
    if isinstance(param, dict) and "code" in param:
        param["code"] = "******"
    if "code" in data and not isinstance(data["code"], dict):
        data["code"] = "******"
    return data


def record_sms_send(
    *,
    site_id: int | None,
    phone: str,
    scene: str,
    provider: str,
    status: str,
    template_code: str | None = None,
    sign_name: str | None = None,
    provider_code: str | None = None,
    provider_message: str | None = None,
    request_json: dict[str, Any] | None = None,
    response_json: dict[str, Any] | None = None,
) -> None:
    """独立提交一条发送记录，主流程回滚时仍然保留。"""
    if site_id is None:
        return
    db = db_module.SessionLocal()
    try:
        db.add(
            SmsSendLog(
                site_id=site_id,
                phone=phone,
                scene=scene or "otp",
                provider=provider,
                template_code=template_code,
                sign_name=sign_name,
                status=status,
                provider_code=(provider_code or None),
                provider_message=(provider_message or "")[:512] or None,
                request_json=mask_sms_payload(request_json),
                response_json=response_json,
            )
        )
        db.commit()
    except Exception:
        logger.exception("写入短信发送记录失败")
        db.rollback()
    finally:
        db.close()
