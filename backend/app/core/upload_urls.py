"""上传对象公开地址与旧 /api/v1/files/ 路径识别。"""

from __future__ import annotations

import re

from app.core.config import get_settings

OBJECT_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|pdf)$")
IMAGE_OBJECT_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
LEGACY_IMAGE_RE = re.compile(r"^/api/v1/files/([0-9a-f]{32}\.(jpg|png|webp))$")
MEDIA_IMAGE_RE = re.compile(r"^/media/([0-9a-f]{32}\.(jpg|png|webp))$")
# 库内旧前缀（file 域证书未覆盖时浏览器打不开）一律改成当前 FILE_PUBLIC_BASE_URL
IMAGE_URL_IN_TEXT = re.compile(
    r"(?:https?://file\.guanyespace\.com|https?://localhost:8900/public|"
    r"https?://127\.0\.0\.1:8900/public|/api/v1/files|/media)"
    r"/([0-9a-f]{32}\.(?:jpg|png|webp))"
)
IMAGE_EXTS = {".jpg", ".png", ".webp"}


def file_public_base() -> str:
    return get_settings().file_public_base_url.rstrip("/")


def public_object_url(filename: str) -> str:
    return f"{file_public_base()}/{filename}"


def is_stored_image_url(url: str) -> bool:
    """系统上传图：相对路径 /media、旧 /api/v1/files/、或当前公开前缀。"""
    text = (url or "").strip()
    if not text:
        return False
    if LEGACY_IMAGE_RE.match(text) or MEDIA_IMAGE_RE.match(text):
        return True
    prefix = file_public_base() + "/"
    if text.startswith(prefix) and IMAGE_OBJECT_RE.match(text[len(prefix) :]):
        return True
    return False


def rewrite_legacy_image_text(text: str) -> str:
    """把正文/字段里的旧图片路径换成当前公开 URL。PDF 不改。"""
    base = file_public_base()

    def _repl(match: re.Match[str]) -> str:
        return f"{base}/{match.group(1)}"

    return IMAGE_URL_IN_TEXT.sub(_repl, text)


def rewrite_stored_value(value: object) -> object:
    if isinstance(value, str):
        return rewrite_legacy_image_text(value)
    if isinstance(value, list):
        return [rewrite_stored_value(item) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_stored_value(item) for key, item in value.items()}
    return value
