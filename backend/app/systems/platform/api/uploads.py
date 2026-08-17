"""商户证照等附件上传。"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError

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


def upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _assert_can_upload(ctx: RequestContext) -> None:
    if ctx.is_site_admin or "*" in ctx.permissions or any(
        p in ctx.permissions for p in ("staff:manage", "org:manage", "retail:manage", "coach:manage")
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
    settings = get_settings()
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED.get(content_type)
    if ext is None:
        raise AppError("invalid_file", "仅支持 JPG / PNG / WEBP / PDF", status_code=400)

    data = await file.read()
    if not data:
        raise AppError("invalid_file", "文件为空", status_code=400)
    if len(data) > settings.upload_max_bytes:
        raise AppError("invalid_file", "文件不能超过 8MB", status_code=400)
    if not any(data.startswith(sig) for sig in _MAGIC[ext]):
        raise AppError("invalid_file", "文件内容与类型不符", status_code=400)

    name = f"{uuid4().hex}{ext}"
    dest = upload_root() / name
    dest.write_bytes(data)
    return {"url": f"/api/v1/files/{name}", "filename": name, "content_type": content_type}


@router.get("/files/{filename}")
def get_uploaded_file(filename: str):
    """读取已上传附件。文件名为 UUID，避免枚举。"""
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise AppError("not_found", "文件不存在", status_code=404)
    path = upload_root() / filename
    if not path.is_file():
        raise AppError("not_found", "文件不存在", status_code=404)
    return FileResponse(path)
