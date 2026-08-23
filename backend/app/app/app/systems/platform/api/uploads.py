"""商户证照等附件上传。"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.core.deps import RequestContext, bearer_scheme, get_current_context
from app.core.errors import AppError
from app.core.security import decode_access_token

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
_IMAGE_EXTS = {".jpg", ".png", ".webp"}


def upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


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
    """校验并落盘上传文件，返回可访问 URL。"""
    settings = get_settings()
    if not data:
        raise AppError("invalid_file", "文件为空", status_code=400)
    if len(data) > settings.upload_max_bytes:
        raise AppError("invalid_file", "文件不能超过 8MB", status_code=400)

    mime = (content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED.get(mime) or _ext_from_magic(data)
    if images_only:
        if ext not in _IMAGE_EXTS:
            raise AppError("invalid_file", "头像仅支持 JPG / PNG / WEBP", status_code=400)
    elif ext is None:
        raise AppError("invalid_file", "仅支持 JPG / PNG / WEBP / PDF", status_code=400)
    if ext is None:
        raise AppError("invalid_file", "仅支持 JPG / PNG / WEBP / PDF", status_code=400)

    if not _matches_magic(ext, data):
        raise AppError("invalid_file", "文件内容与类型不符", status_code=400)

    name = f"{uuid4().hex}{ext}"
    dest = upload_root() / name
    dest.write_bytes(data)
    return {"url": f"/api/v1/files/{name}", "filename": name, "content_type": mime or f"image/{ext[1:]}"}


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
    """读取已上传附件。图片可公开（H5/小程序 <img>），PDF 需登录。"""
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise AppError("not_found", "文件不存在", status_code=404)
    path = upload_root() / filename
    if not path.is_file():
        raise AppError("not_found", "文件不存在", status_code=404)
    if path.suffix.lower() not in _IMAGE_EXTS:
        if creds is None or not creds.credentials:
            raise AppError("unauthorized", "证照文件需登录后查看", status_code=401)
        try:
            decode_access_token(creds.credentials)
        except ValueError as exc:
            raise AppError("unauthorized", "令牌无效", status_code=401) from exc
    return FileResponse(path)
