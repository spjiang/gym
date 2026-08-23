"""场地门户资料：观野SPACE 整体介绍、客服与广告位。"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.systems.platform.models.org import Site
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/site/profile", tags=["site-profile"])

_IMAGE_RE = re.compile(r"^/api/v1/files/[0-9a-f]{32}\.(jpg|png|webp)$")
MAX_BANNERS = 6
MAX_GALLERY = 9


class SiteProfileOut(BaseModel):
    id: int
    name: str
    tagline: str | None = None
    description: str | None = None
    address: str | None = None
    service_phone: str | None = None
    business_hours: str | None = None
    cover_image_url: str | None = None
    banner_image_urls: list[str] = Field(default_factory=list)
    gallery_image_urls: list[str] = Field(default_factory=list)


class SiteProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    tagline: str | None = Field(default=None, max_length=128)
    description: str | None = None
    address: str | None = Field(default=None, max_length=255)
    service_phone: str | None = Field(default=None, max_length=32)
    business_hours: str | None = Field(default=None, max_length=128)
    cover_image_url: str | None = Field(default=None, max_length=255)
    banner_image_urls: list[str] = Field(default_factory=list)
    gallery_image_urls: list[str] = Field(default_factory=list)


def _blank(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _normalize_image(url: str | None, *, field: str) -> str | None:
    text = _blank(url)
    if text is None:
        return None
    if not _IMAGE_RE.match(text):
        raise AppError("invalid_image", f"{field}地址无效，请通过系统上传", status_code=400)
    return text


def _normalize_images(urls: list[str] | None, *, field: str, limit: int) -> list[str]:
    out: list[str] = []
    for raw in urls or []:
        url = _normalize_image(raw, field=field)
        if url and url not in out:
            out.append(url)
    if len(out) > limit:
        raise AppError("too_many_images", f"{field}最多 {limit} 张", status_code=400)
    return out


def site_profile_out(row: Site) -> SiteProfileOut:
    return SiteProfileOut(
        id=row.id,
        name=row.name,
        tagline=row.tagline,
        description=row.description,
        address=row.address,
        service_phone=row.service_phone,
        business_hours=row.business_hours,
        cover_image_url=row.cover_image_url,
        banner_image_urls=list(row.banner_image_urls or []),
        gallery_image_urls=list(row.gallery_image_urls or []),
    )


@router.get("", response_model=SiteProfileOut)
def get_site_profile(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("org:read", "*")
    row = db.get(Site, ctx.site_id)
    if row is None:
        raise AppError("not_found", "场地不存在", status_code=404)
    return site_profile_out(row)


@router.put("", response_model=SiteProfileOut)
def put_site_profile(
    body: SiteProfileIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """场地级门户资料，仅超管可改。"""
    ctx.require_permission("org:write", "*")
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可编辑观野SPACE 介绍", status_code=403)
    row = db.get(Site, ctx.site_id)
    if row is None:
        raise AppError("not_found", "场地不存在", status_code=404)
    row.name = body.name.strip()
    row.tagline = _blank(body.tagline)
    row.description = _blank(body.description)
    row.address = _blank(body.address)
    row.service_phone = _blank(body.service_phone)
    row.business_hours = _blank(body.business_hours)
    row.cover_image_url = _normalize_image(body.cover_image_url, field="封面图")
    row.banner_image_urls = _normalize_images(body.banner_image_urls, field="广告图", limit=MAX_BANNERS)
    row.gallery_image_urls = _normalize_images(body.gallery_image_urls, field="环境图", limit=MAX_GALLERY)
    write_audit(
        db,
        action="site.profile_update",
        target_type="site",
        target_id=row.id,
        summary="更新观野SPACE 门户介绍",
        actor_staff_id=ctx.staff.id,
        site_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return site_profile_out(row)
