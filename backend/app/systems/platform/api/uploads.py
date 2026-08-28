"""商户证照等附件上传。写入 MinIO，图片返回公开 URL。"""

from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.core.deps import RequestContext, bearer_scheme, get_current_context
from app.core.errors import AppError
from app.core.object_store import PRIVATE_BUCKET, PUBLIC_BUCKET, get_bytes, object_exists, put_bytes
from app.core.security import decode_access_token
from app.core.upload_urls import IMAGE_EXTS, OBJECT_NAME_RE, public_object_url

router = APIRouter(tags=["uploads"])

_ALLOWED = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
_MAGIC = {
    ".jpg": (b"\xff\xd8",),
    ".png": (b"\x89PNG",),
    ".webp": (b"RIFF",),
    ".pdf": (b"%PDF",),
}
_MIME = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def _ext_from_magic(data: bytes) -> str | None:
    """按文件头识别类型，兼容小程序上传时 Content-Type 为空或 octet-stream。"""
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return ".webp"
    if data.startswith(b"%PDF"):
        return ".pdf"
    return None


def _matches_magic(ext: str, data: bytes) -> bool:
    if ext == ".webp":
        return data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return any(data.startswith(sig) for sig in _MAGIC.get(ext, ()))


def persist_upload(data: bytes, content_type: str | None, *, images_only: bool = False) -> dict:
    """校验并写入 MinIO，返回可访问 URL。"""
    settings = get_settings()
    if not data:
        raise AppError("invalid_file", "文件为空", status_code=400)
    if len(data) > settings.upload_max_bytes:
        raise AppError("invalid_file", "文件不能超过 8MB", status_code=400)

    mime = (content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED.get(mime) or _ext_from_magic(data)
    if images_only:
        if ext not in IMAGE_EXTS:
            raise AppError("invalid_file", "头像仅支持 JPG / PNG / WEBP", status_code=400)
    elif ext is None:
        raise AppError("invalid_file", "仅支持 JPG / PNG / WEBP / PDF", status_code=400)
    if ext is None:
        raise AppError("invalid_file", "仅支持 JPG / PNG / WEBP / PDF", status_code=400)

    if not _matches_magic(ext, data):
        raise AppError("invalid_file", "文件内容与类型不符", status_code=400)

    name = f"{uuid4().hex}{ext}"
    bucket = PUBLIC_BUCKET if ext in IMAGE_EXTS else PRIVATE_BUCKET
    stored_type = mime if mime in _ALLOWED else _MIME[ext]
    put_bytes(bucket, name, data, stored_type)
    url = public_object_url(name) if ext in IMAGE_EXTS else f"/api/v1/files/{name}"
    return {"url": url, "filename": name, "content_type": stored_type}


async def save_upload_file(file: UploadFile, *, images_only: bool = False) -> dict:
    data = await file.read()
    return persist_upload(data, file.content_type, images_only=images_only)


def _assert_can_upload(ctx: RequestContext) -> None:
    if ctx.is_site_admin or "*" in ctx.permissions or any(
        p in ctx.permissions
        for p in (
            "staff:manage",
            "org:manage",
            "retail:manage",
            "coach:manage",
            "activity:manage",
            "catering:manage",
            "website:manage",
        )
    ):
        return
    raise AppError("forbidden", "无权上传附件", status_code=403)


@router.post("/uploads")
async def upload_file(
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(get_current_context),
):
    """上传营业执照等附件，返回可访问 URL。"""
    _assert_can_upload(ctx)
    return await save_upload_file(file)


@router.get("/files/{filename}")
def get_uploaded_file(
    filename: str,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """读取已上传附件。图片 302 到公开域；PDF 需登录后从私有桶读取。"""
    if not OBJECT_NAME_RE.fullmatch(filename):
        raise AppError("not_found", "文件不存在", status_code=404)
    ext = f".{filename.rsplit('.', 1)[-1].lower()}"
    if ext in IMAGE_EXTS:
        if not object_exists(PUBLIC_BUCKET, filename):
            raise AppError("not_found", "文件不存在", status_code=404)
        return RedirectResponse(public_object_url(filename), status_code=302)
    if creds is None or not creds.credentials:
        raise AppError("unauthorized", "证照文件需登录后查看", status_code=401)
    try:
        decode_access_token(creds.credentials)
    except ValueError as exc:
        raise AppError("unauthorized", "令牌无效", status_code=401) from exc
    if not object_exists(PRIVATE_BUCKET, filename):
        raise AppError("not_found", "文件不存在", status_code=404)
    return Response(content=get_bytes(PRIVATE_BUCKET, filename), media_type="application/pdf")
