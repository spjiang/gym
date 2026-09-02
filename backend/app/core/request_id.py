"""请求级 request_id。"""

from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_error_recorded: ContextVar[bool] = ContextVar("error_recorded", default=False)


def set_request_id(value: str | None) -> None:
    _request_id.set(value)
    if value is None:
        _error_recorded.set(False)


def get_request_id() -> str | None:
    return _request_id.get()


def error_already_recorded() -> bool:
    return _error_recorded.get()


def mark_error_recorded() -> None:
    _error_recorded.set(True)
