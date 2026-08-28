"""官网员工端：设置与文章。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.paging import PageIn, PageOut, paginate
from app.systems.platform.models.org import Site
from app.systems.platform.models.website import WebsiteArticle
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.website import (
    STATUSES,
    article_out,
    assert_channel,
    clip_text,
    get_or_create_settings,
    get_settings_row,
    mark_published,
    merge_json,
    normalize_brands_json,
    normalize_home_json,
    normalize_image,
    normalize_site_json,
    require_site_wide,
    staff_settings_payload,
)

router = APIRouter(prefix="/website", tags=["website"])


class SettingsPut(BaseModel):
    site: dict[str, Any] | None = None
    home: dict[str, Any] | None = None
    brands: dict[str, Any] | None = None


class ArticleIn(BaseModel):
    channel: str
    title: str = Field(min_length=1, max_length=160)
    summary: str | None = Field(default=None, max_length=255)
    cover_image_url: str | None = None
    body: str | None = None
    contact_hint: str | None = Field(default=None, max_length=255)
    sort_order: int = 0


class ArticlePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    summary: str | None = Field(default=None, max_length=255)
    cover_image_url: str | None = None
    body: str | None = None
    contact_hint: str | None = Field(default=None, max_length=255)
    sort_order: int | None = None
    channel: str | None = None


def _require_read(ctx: RequestContext) -> None:
    ctx.require_permission("website:read", "website:manage", "*")


def _require_write(ctx: RequestContext) -> None:
    ctx.require_permission("website:manage", "*")
    require_site_wide(ctx)


def _site_row(db: Session, site_id: int) -> Site:
    row = db.get(Site, site_id)
    if row is None:
        raise AppError("not_found", "场地不存在", status_code=404)
    return row


def _get_article(db: Session, article_id: int, site_id: int) -> WebsiteArticle:
    row = db.get(WebsiteArticle, article_id)
    if row is None or row.site_id != site_id:
        raise AppError("not_found", "文章不存在", status_code=404)
    return row


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_read(ctx)
    site = _site_row(db, ctx.site_id)
    return staff_settings_payload(get_settings_row(db, ctx.site_id), site)


@router.put("/settings")
def put_settings(
    body: SettingsPut,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_write(ctx)
    if body.site is None and body.home is None and body.brands is None:
        raise AppError("empty_patch", "请提交 site / home / brands 至少一块", status_code=400)
    site = _site_row(db, ctx.site_id)
    row = get_or_create_settings(db, ctx.site_id, staff_id=ctx.staff.id)
    if body.site is not None:
        row.site_json = merge_json(row.site_json, normalize_site_json(body.site))
    if body.home is not None:
        row.home_json = merge_json(row.home_json, normalize_home_json(body.home))
    if body.brands is not None:
        incoming = normalize_brands_json(body.brands)
        existing = dict(row.brands_json or {})
        for key, block in incoming.items():
            existing[key] = merge_json(existing.get(key), block)
        row.brands_json = existing
    row.updated_by_staff_id = ctx.staff.id
    write_audit(
        db,
        action="website.settings_update",
        target_type="website_settings",
        target_id=row.id,
        summary="更新官网配置",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return staff_settings_payload(row, site)


@router.get("/articles")
def list_articles(
    channel: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_read(ctx)
    stmt = select(WebsiteArticle).where(WebsiteArticle.site_id == ctx.site_id)
    if channel:
        stmt = stmt.where(WebsiteArticle.channel == assert_channel(channel))
    if status:
        if status not in STATUSES:
            raise AppError("invalid_status", "状态无效", status_code=400)
        stmt = stmt.where(WebsiteArticle.status == status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(WebsiteArticle.title.ilike(like), WebsiteArticle.summary.ilike(like)))
    stmt = stmt.order_by(
        WebsiteArticle.sort_order.desc(),
        WebsiteArticle.published_at.desc(),
        WebsiteArticle.id.desc(),
    )
    paging = PageIn(page=page, page_size=page_size)
    rows, total = paginate(db, stmt, page=paging.page, page_size=paging.page_size)
    return PageOut(items=[article_out(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.post("/articles")
def create_article(
    body: ArticleIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_write(ctx)
    channel = assert_channel(body.channel)
    row = WebsiteArticle(
        site_id=ctx.site_id,
        channel=channel,
        title=body.title.strip(),
        summary=clip_text(body.summary, limit=255),
        cover_image_url=normalize_image(body.cover_image_url, field="封面"),
        body=(body.body or "").strip(),
        contact_hint=clip_text(body.contact_hint, limit=255),
        status="draft",
        sort_order=body.sort_order,
        updated_by_staff_id=ctx.staff.id,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="website.article_create",
        target_type="website_article",
        target_id=row.id,
        summary=f"创建官网文章 {row.title}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return article_out(row)


@router.patch("/articles/{article_id}")
def patch_article(
    article_id: int,
    body: ArticlePatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_write(ctx)
    if body.channel is not None:
        raise AppError("channel_immutable", "频道创建后不可修改", status_code=400)
    row = _get_article(db, article_id, ctx.site_id)
    if body.title is not None:
        row.title = body.title.strip()
    if body.summary is not None:
        row.summary = clip_text(body.summary, limit=255)
    if "cover_image_url" in body.model_fields_set:
        row.cover_image_url = normalize_image(body.cover_image_url, field="封面")
    if body.body is not None:
        row.body = body.body.strip()
    if body.contact_hint is not None:
        row.contact_hint = clip_text(body.contact_hint, limit=255)
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    row.updated_by_staff_id = ctx.staff.id
    write_audit(
        db,
        action="website.article_update",
        target_type="website_article",
        target_id=row.id,
        summary=f"更新官网文章 {row.title}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return article_out(row)


@router.post("/articles/{article_id}/publish")
def publish_article(
    article_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_write(ctx)
    row = _get_article(db, article_id, ctx.site_id)
    mark_published(row)
    row.updated_by_staff_id = ctx.staff.id
    write_audit(
        db,
        action="website.article_publish",
        target_type="website_article",
        target_id=row.id,
        summary=f"发布官网文章 {row.title}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return article_out(row)


@router.post("/articles/{article_id}/archive")
def archive_article(
    article_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_write(ctx)
    row = _get_article(db, article_id, ctx.site_id)
    row.status = "archived"
    row.updated_by_staff_id = ctx.staff.id
    write_audit(
        db,
        action="website.article_archive",
        target_type="website_article",
        target_id=row.id,
        summary=f"下架官网文章 {row.title}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return article_out(row)


@router.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_write(ctx)
    row = _get_article(db, article_id, ctx.site_id)
    title = row.title
    db.delete(row)
    write_audit(
        db,
        action="website.article_delete",
        target_type="website_article",
        target_id=article_id,
        summary=f"删除官网文章 {title}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    return {"ok": True}
