"""HTTP 层自动审计：覆盖全部写操作与会员端/H5/小程序请求。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core import db as db_module
from app.core.audit_context import AuditEnvelope, set_audit_envelope
from app.core.request_id import get_request_id
from app.core.security import decode_access_token
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import Member
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.audit_catalog import (
    CLIENT_CHANNEL_LABELS,
    extract_path_target_id,
    infer_client_channel,
    resolve_route_meta,
    sanitize_audit_payload,
    should_auto_audit,
)

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {"password", "old_password", "new_password", "token", "access_token", "api_key"}


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _decode_token(request: Request) -> dict[str, Any] | None:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    try:
        return decode_access_token(token)
    except ValueError:
        return None


def _load_actor(db, payload: dict[str, Any] | None) -> tuple[str | None, int | None, int | None, str | None, str | None, int | None]:
    if not payload:
        return None, None, None, None, None, None
    typ = payload.get("typ")
    sub = payload.get("sub")
    if sub is None:
        return typ, None, None, None, None, None
    actor_id = int(sub)
    if typ == "member":
        member = db.get(Member, actor_id)
        if member is None:
            return typ, None, actor_id, None, None, None
        return typ, None, actor_id, member.name, member.phone, member.site_id
    staff = db.get(StaffUser, actor_id)
    if staff is None:
        return typ, actor_id, None, None, None, None
    return typ, actor_id, None, staff.display_name, staff.username, staff.site_id


def _parse_body_for_context(body: bytes, content_type: str | None) -> dict[str, Any] | None:
    if not body:
        return None
    ctype = (content_type or "").lower()
    if "json" not in ctype:
        return {"_note": "非 JSON 请求体已省略"}
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"_note": "请求体解析失败"}
    if isinstance(data, dict):
        return sanitize_audit_payload(data)
    return {"_value": data}


def _build_envelope(request: Request, body: bytes | None = None) -> AuditEnvelope:
    path = request.url.path
    method = request.method.upper()
    route_meta = resolve_route_meta(path)
    payload = _decode_token(request)
    token_typ = payload.get("typ") if payload else None
    has_device = bool(request.headers.get("x-device-code"))
    client_channel = infer_client_channel(
        header_value=request.headers.get("x-client-channel"),
        user_agent=request.headers.get("user-agent"),
        has_device_headers=has_device,
        token_typ=token_typ,
        path=path,
    )
    env = AuditEnvelope(
        http_method=method,
        request_path=path,
        client_ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        client_channel=client_channel,
        subsystem_code=route_meta.subsystem_code,
        module=route_meta.module,
    )
    db = db_module.SessionLocal()
    try:
        typ, staff_id, member_id, name, account, site_id = _load_actor(db, payload)
        env.actor_type = "member" if typ == "member" else ("staff" if staff_id else None)
        env.actor_staff_id = staff_id
        env.actor_member_id = member_id
        env.actor_name = name
        env.actor_account = account
        env.site_id = site_id
    finally:
        db.close()

    query = dict(request.query_params)
    if query:
        env.detail["query"] = sanitize_audit_payload(query) or {}
    if body is not None:
        parsed = _parse_body_for_context(body, request.headers.get("content-type"))
        if parsed:
            env.detail["body"] = parsed
            mid = parsed.get("merchant_id")
            if isinstance(mid, int):
                env.merchant_id = mid
            elif isinstance(mid, str) and mid.isdigit():
                env.merchant_id = int(mid)
    return env


def _auto_summary(env: AuditEnvelope) -> str:
    channel = CLIENT_CHANNEL_LABELS.get(env.client_channel or "", env.client_channel or "未知")
    actor = env.actor_name or env.actor_account or "匿名"
    module = env.module or "未知模块"
    status = env.status_code if env.status_code is not None else "?"
    return f"[{channel}] {actor} · {module} · {env.http_method} {env.request_path} → {status}"


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not should_auto_audit(request.method, request.url.path):
            return await call_next(request)

        content_type = (request.headers.get("content-type") or "").lower()
        is_multipart = "multipart/form-data" in content_type
        body = b"" if is_multipart else await request.body()
        started = time.perf_counter()
        env = _build_envelope(request, body if body else None)
        env.request_id = get_request_id()
        set_audit_envelope(env)

        if is_multipart:
            response = await call_next(request)
        else:

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request = Request(request.scope, receive)
            response = await call_next(request)
        env.duration_ms = int((time.perf_counter() - started) * 1000)
        env.status_code = response.status_code
        env.status = "success" if response.status_code < 400 else "failure"

        if env.skip_auto:
            set_audit_envelope(None)
            return response

        db = db_module.SessionLocal()
        try:
            action = f"http.{request.method.lower()}"
            write_audit(
                db,
                action=action,
                target_type="http_request",
                target_id=extract_path_target_id(request.url.path),
                summary=_auto_summary(env),
                actor_staff_id=env.actor_staff_id,
                actor_member_id=env.actor_member_id,
                actor_type=env.actor_type or ("anonymous" if not env.actor_staff_id and not env.actor_member_id else "system"),
                actor_name=env.actor_name,
                actor_account=env.actor_account,
                site_id=env.site_id,
                merchant_id=env.merchant_id,
                subsystem_code=env.subsystem_code,
                module=env.module,
                client_channel=env.client_channel,
                http_method=env.http_method,
                request_path=env.request_path,
                client_ip=env.client_ip,
                user_agent=env.user_agent,
                status=env.status,
                status_code=env.status_code,
                duration_ms=env.duration_ms,
                request_id=env.request_id,
                detail_json=env.detail or None,
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("自动审计写入失败 path=%s", request.url.path)
        finally:
            db.close()
            set_audit_envelope(None)
        return response
