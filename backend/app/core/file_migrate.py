"""启动时把 UPLOAD_DIR 旧文件迁入 MinIO，并改写库里图片 URL。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.core import db as db_module
from app.core.object_store import PRIVATE_BUCKET, PUBLIC_BUCKET, object_exists, put_bytes
from app.core.upload_urls import IMAGE_EXTS, OBJECT_NAME_RE, rewrite_stored_value
from app.systems.catering.models.catering import CateringMenuItem
from app.systems.gym.models.activity import Activity
from app.systems.gym.models.course import Coach
from app.systems.gym.models.retail import RetailSku
from app.systems.platform.models.member import Member
from app.systems.platform.models.org import Merchant, Site
from app.systems.platform.models.website import WebsiteArticle, WebsiteSettings

_MIME = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def _upload_root() -> Path:
    return Path(get_settings().upload_dir)


def migrate_disk_files() -> int:
    """扫描 UPLOAD_DIR 一层文件，已存在的对象跳过。返回新上传数量。"""
    root = _upload_root()
    if not root.is_dir():
        return 0
    uploaded = 0
    for path in root.iterdir():
        if not path.is_file() or not OBJECT_NAME_RE.fullmatch(path.name):
            continue
        ext = path.suffix.lower()
        bucket = PUBLIC_BUCKET if ext in IMAGE_EXTS else PRIVATE_BUCKET
        if object_exists(bucket, path.name):
            continue
        put_bytes(bucket, path.name, path.read_bytes(), _MIME[ext])
        uploaded += 1
    return uploaded


def _assign_if_changed(row: object, attr: str) -> bool:
    current = getattr(row, attr)
    rewritten = rewrite_stored_value(current)
    if rewritten == current:
        return False
    setattr(row, attr, rewritten)
    if attr.endswith("_json"):
        flag_modified(row, attr)
    return True


def rewrite_database_urls(db: Session) -> int:
    """把仍指向旧前缀的图片字段改成当前 FILE_PUBLIC_BASE_URL。"""
    changed = 0
    for row in db.scalars(select(Site)).all():
        for attr in ("cover_image_url", "banner_image_urls", "gallery_image_urls"):
            if _assign_if_changed(row, attr):
                changed += 1
    for row in db.scalars(select(Merchant)).all():
        for attr in ("cover_image_url", "gallery_image_urls", "license_image_url"):
            if _assign_if_changed(row, attr):
                changed += 1
    for row in db.scalars(select(Member)).all():
        if _assign_if_changed(row, "avatar_url"):
            changed += 1
    for row in db.scalars(select(Coach)).all():
        for attr in ("avatar_url", "intro_image_urls"):
            if _assign_if_changed(row, attr):
                changed += 1
    for row in db.scalars(select(Activity)).all():
        if _assign_if_changed(row, "cover_url"):
            changed += 1
    for row in db.scalars(select(RetailSku)).all():
        if _assign_if_changed(row, "image_urls"):
            changed += 1
    for row in db.scalars(select(CateringMenuItem)).all():
        if _assign_if_changed(row, "image_url"):
            changed += 1
    for row in db.scalars(select(WebsiteSettings)).all():
        for attr in ("site_json", "home_json", "brands_json"):
            if _assign_if_changed(row, attr):
                changed += 1
    for row in db.scalars(select(WebsiteArticle)).all():
        for attr in ("cover_image_url", "body"):
            if _assign_if_changed(row, attr):
                changed += 1
    if changed:
        db.commit()
    return changed


def migrate_local_uploads() -> None:
    """建桶后扫盘并改库。MinIO 不可达时由调用方失败退出。"""
    migrate_disk_files()
    db = db_module.SessionLocal()
    try:
        rewrite_database_urls(db)
    finally:
        db.close()
