"""统一错误响应。"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.audit_context import merge_audit_detail
from app.core.request_id import get_request_id


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


def _with_request_id(response: JSONResponse) -> JSONResponse:
    rid = get_request_id()
    if rid:
        response.headers["X-Request-ID"] = rid
    return response


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        merge_audit_detail(error_code=exc.code, message=exc.message)
        from app.systems.platform.services.error_events import record_error, should_persist_app_error

        if should_persist_app_error(exc):
            record_error(
                error_code=exc.code,
                message=exc.message,
                status_code=exc.status_code,
                request=request,
                exc=exc,
            )
        return _with_request_id(
            JSONResponse(
                status_code=exc.status_code,
                content={"code": exc.code, "message": exc.message},
            )
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        message = str(detail) if not isinstance(detail, dict) else str(detail)
        merge_audit_detail(error_code="http_error", message=message)
        if exc.status_code >= 500:
            from app.systems.platform.services.error_events import record_error

            record_error(
                error_code="http_error",
                message=message,
                status_code=exc.status_code,
                request=request,
                extra={"detail": detail} if isinstance(detail, dict) else None,
            )
        if isinstance(detail, dict):
            return _with_request_id(JSONResponse(status_code=exc.status_code, content=detail))
        return _with_request_id(
            JSONResponse(
                status_code=exc.status_code,
                content={"code": "http_error", "message": str(detail)},
            )
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        merge_audit_detail(error_code="validation_error", message="请求参数校验失败")
        return _with_request_id(
            JSONResponse(
                status_code=422,
                content={"code": "validation_error", "message": "请求参数校验失败", "details": exc.errors()},
            )
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        import logging

        logging.getLogger(__name__).exception(
            "未捕获异常 path=%s request_id=%s", request.url.path, get_request_id()
        )
        from app.systems.platform.services.error_events import record_error

        record_error(
            error_code="internal_error",
            message=str(exc) or "服务器内部错误",
            status_code=500,
            request=request,
            exc=exc,
        )
        merge_audit_detail(error_code="internal_error", message="服务器内部错误")
        return _with_request_id(
            JSONResponse(
                status_code=500,
                content={"code": "internal_error", "message": "服务器内部错误"},
            )
        )
