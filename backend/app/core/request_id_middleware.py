"""为每个请求分配 request_id，并回写响应头。"""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.request_id import set_request_id

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = (request.headers.get("x-request-id") or "").strip()
        rid = incoming[:64] if incoming else uuid.uuid4().hex
        set_request_id(rid)
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # BaseHTTPMiddleware 会把路由异常再次抛出，这里收口为 500
                logger.exception("未捕获异常 path=%s request_id=%s", request.url.path, rid)
                from app.systems.platform.services.error_events import record_error

                record_error(
                    error_code="internal_error",
                    message=str(exc) or "服务器内部错误",
                    status_code=500,
                    request=request,
                    exc=exc,
                )
                response = JSONResponse(
                    status_code=500,
                    content={"code": "internal_error", "message": "服务器内部错误"},
                )
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            set_request_id(None)
