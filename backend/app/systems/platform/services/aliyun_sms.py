"""阿里云短信 SendSms（dysmsapi 2017-05-25）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.core.errors import AppError

_ENDPOINT = "https://dysmsapi.aliyuncs.com/"


def _percent(value: str) -> str:
    return quote(str(value), safe="-_.~")


def call_aliyun_sms(
    *,
    access_key_id: str,
    access_key_secret: str,
    phone: str,
    sign_name: str,
    template_code: str,
    template_param: dict,
) -> dict:
    """调用 SendSms 并返回阿里云 JSON。网络失败或返回非 JSON 时抛出错误。"""
    params = {
        "AccessKeyId": access_key_id,
        "Action": "SendSms",
        "Format": "JSON",
        "PhoneNumbers": phone,
        "RegionId": "cn-hangzhou",
        "SignName": sign_name,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": uuid.uuid4().hex,
        "SignatureVersion": "1.0",
        "TemplateCode": template_code,
        "TemplateParam": json.dumps(template_param, ensure_ascii=False, separators=(",", ":")),
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Version": "2017-05-25",
    }
    canonical = "&".join(f"{_percent(k)}={_percent(params[k])}" for k in sorted(params))
    string_to_sign = f"POST&{_percent('/')}&{_percent(canonical)}"
    digest = hmac.new(
        f"{access_key_secret}&".encode(),
        string_to_sign.encode(),
        hashlib.sha1,
    ).digest()
    params["Signature"] = base64.b64encode(digest).decode()
    try:
        resp = httpx.post(_ENDPOINT, data=params, timeout=10.0)
    except httpx.HTTPError as exc:
        raise AppError("otp_send_failed", f"阿里云短信不可达: {exc}", status_code=502) from exc
    try:
        body = resp.json()
    except ValueError as exc:
        raise AppError("otp_send_failed", "阿里云短信返回无法解析", status_code=502) from exc
    if not isinstance(body, dict):
        raise AppError("otp_send_failed", "阿里云短信返回无法解析", status_code=502)
    return body


def send_aliyun_sms(
    *,
    access_key_id: str,
    access_key_secret: str,
    phone: str,
    sign_name: str,
    template_code: str,
    template_param: dict,
) -> dict:
    """按阿里云 RPC 签名调用 SendSms，业务状态非 OK 时抛出错误。"""
    body = call_aliyun_sms(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        phone=phone,
        sign_name=sign_name,
        template_code=template_code,
        template_param=template_param,
    )
    if body.get("Code") != "OK":
        message = body.get("Message") or body.get("Code") or "发送失败"
        raise AppError("otp_send_failed", f"阿里云短信失败: {message}", status_code=502)
    return body
