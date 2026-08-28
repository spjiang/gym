"""会员 H5 对外链接：统一读取 MEMBER_WEB_PUBLIC_URL，本地/线上由 .env 区分。"""

from __future__ import annotations

from urllib.parse import urlencode, urlsplit, urlunsplit

from app.core.config import get_settings


def member_h5_base_url() -> str:
    """会员 H5 根地址（无尾斜杠）。"""
    return get_settings().member_web_public_url.strip().rstrip("/")


def member_h5_path_url(path: str, *, query: dict[str, str | int] | None = None) -> str:
    """拼接会员 H5 路径与查询参数。"""
    normalized = (path or "/").strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    url = f"{member_h5_base_url()}{normalized}"
    if not query:
        return url
    parts = urlsplit(url)
    sep = "&" if parts.query else ""
    encoded = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, f"{parts.query}{sep}{encoded}", parts.fragment))


def build_promoter_link(
    *,
    code: str,
    landing_path: str | None = None,
    merchant_id: int | None = None,
) -> str:
    """推广码落地链接（管理端/会员端二维码共用）。"""
    path = (landing_path or "/login").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    query: dict[str, str | int] = {"promoter": code}
    if merchant_id is not None:
        query["merchant_id"] = merchant_id
    return member_h5_path_url(path, query=query)


def is_local_member_web_url(url: str | None = None) -> bool:
    """是否仍指向本机地址（生产环境应告警）。"""
    value = (url or member_h5_base_url()).lower()
    return "localhost" in value or "127.0.0.1" in value
