"""官网公开只读接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.schemas.paging import PageIn, PageOut, paginate
from app.systems.platform.models.website import WebsiteArticle
from app.systems.platform.services.website import (
    article_out,
    article_public_brief,
    assert_channel,
    contact_from_site,
    first_site,
    get_settings_row,
    load_latest_news,
    public_brands,
    public_home,
    public_site,
)

router = APIRouter(prefix="/public/website", tags=["public-website"])


@router.get("")
def public_website(db: Session = Depends(get_db)):
    site = first_site(db)
    row = get_settings_row(db, site.id) if site else None
    latest = load_latest_news(db, site.id) if site else []
    return {
        "site": public_site(row.site_json if row else None),
        "home": public_home(row.home_json if row else None),
        "brands": public_brands(row.brands_json if row else None),
        "contact": contact_from_site(site),
        "latest_news": [article_public_brief(n) for n in latest],
    }


@router.get("/articles")
def public_articles(
    channel: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    ch = assert_channel(channel)
    site = first_site(db)
    if site is None:
        return PageOut(items=[], total=0, page=page, page_size=page_size)
    stmt = (
        select(WebsiteArticle)
        .where(
            WebsiteArticle.site_id == site.id,
            WebsiteArticle.channel == ch,
            WebsiteArticle.status == "published",
        )
        .order_by(
            WebsiteArticle.sort_order.desc(),
            WebsiteArticle.published_at.desc(),
            WebsiteArticle.id.desc(),
        )
    )
    paging = PageIn(page=page, page_size=page_size)
    rows, total = paginate(db, stmt, page=paging.page, page_size=paging.page_size)
    return PageOut(
        items=[article_public_brief(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/articles/{article_id}")
def public_article(article_id: int, db: Session = Depends(get_db)):
    site = first_site(db)
    if site is None:
        raise AppError("not_found", "内容不存在", status_code=404)
    row = db.get(WebsiteArticle, article_id)
    if row is None or row.site_id != site.id or row.status != "published":
        raise AppError("not_found", "内容不存在", status_code=404)
    return article_out(row)
