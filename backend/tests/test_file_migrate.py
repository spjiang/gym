"""启动迁移：盘上旧文件进桶。"""

from uuid import uuid4

from sqlalchemy import select

from app.core import db as db_module
from app.core.config import get_settings
from app.core.file_migrate import migrate_disk_files, rewrite_database_urls
from app.core.object_store import PUBLIC_BUCKET, ensure_buckets, object_exists, remove_object
from app.systems.platform.models.org import Site


def test_migrate_disk_png_into_public_bucket(tmp_path, monkeypatch):
    name = f"{uuid4().hex}.png"
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (tmp_path / name).write_bytes(png)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        ensure_buckets()
        assert migrate_disk_files() == 1
        assert migrate_disk_files() == 0
        assert object_exists(PUBLIC_BUCKET, name)
    finally:
        if object_exists(PUBLIC_BUCKET, name):
            remove_object(PUBLIC_BUCKET, name)
        get_settings.cache_clear()


def test_rewrite_database_legacy_cover(client):
    name = f"{'f' * 32}.jpg"
    db = db_module.SessionLocal()
    try:
        site = db.scalars(select(Site)).first()
        assert site is not None
        site.cover_image_url = f"/api/v1/files/{name}"
        db.commit()
        rewrite_database_urls(db)
        db.refresh(site)
        base = get_settings().file_public_base_url.rstrip("/")
        assert site.cover_image_url == f"{base}/{name}"
    finally:
        db.close()

